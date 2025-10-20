from fastapi import FastAPI, APIRouter, HTTPException, Depends, Response, Cookie, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import requests
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

# ===== MODELS =====
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    picture: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MoodPulse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    emotion: str
    text: str
    voice_url: Optional[str] = None
    sentiment: Optional[str] = None
    location: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Circle(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    emotion: str
    members: List[str] = []
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CircleMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    circle_id: str
    user_id: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class VoiceDrop(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    voice_url: str
    emotion: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ===== INPUT MODELS =====
class SessionExchangeInput(BaseModel):
    session_id: str

class PulseInput(BaseModel):
    emotion: str
    text: str
    location: Optional[str] = None

class CircleMessageInput(BaseModel):
    message: str

class VoiceDropInput(BaseModel):
    voice_url: str
    emotion: str

# ===== AUTH HELPER =====
async def get_current_user(request: Request) -> User:
    # Try cookie first
    session_token = request.cookies.get("session_token")
    
    # Fallback to Authorization header
    if not session_token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            session_token = auth_header.replace("Bearer ", "")
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Check session validity
    session = await db.user_sessions.find_one({
        "session_token": session_token,
        "expires_at": {"$gt": datetime.now(timezone.utc).isoformat()}
    })
    
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    
    # Get user
    user_doc = await db.users.find_one({"id": session["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    return User(**user_doc)

# ===== AUTH ENDPOINTS =====
@api_router.post("/auth/session")
async def exchange_session(input: SessionExchangeInput, response: Response):
    try:
        # Exchange session_id for session data
        res = requests.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": input.session_id},
            timeout=10
        )
        
        if res.status_code != 200:
            raise HTTPException(status_code=400, detail="Invalid session ID")
        
        data = res.json()
        
        # Check if user exists
        existing_user = await db.users.find_one({"email": data["email"]}, {"_id": 0})
        
        if not existing_user:
            # Create new user
            user = User(
                id=str(uuid.uuid4()),
                email=data["email"],
                name=data["name"],
                picture=data["picture"]
            )
            user_dict = user.model_dump()
            user_dict["created_at"] = user_dict["created_at"].isoformat()
            await db.users.insert_one(user_dict)
        else:
            user = User(**existing_user)
        
        # Create session
        session = UserSession(
            user_id=user.id,
            session_token=data["session_token"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        session_dict = session.model_dump()
        session_dict["expires_at"] = session_dict["expires_at"].isoformat()
        session_dict["created_at"] = session_dict["created_at"].isoformat()
        await db.user_sessions.insert_one(session_dict)
        
        # Set cookie
        response.set_cookie(
            key="session_token",
            value=data["session_token"],
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=7*24*60*60
        )
        
        return {"user": user.model_dump(), "session_token": data["session_token"]}
    except Exception as e:
        logging.error(f"Session exchange error: {e}")
        raise HTTPException(status_code=500, detail="Session exchange failed")

@api_router.get("/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}

# ===== PULSE ENDPOINTS =====
@api_router.post("/pulse", response_model=MoodPulse)
async def create_pulse(input: PulseInput, current_user: User = Depends(get_current_user)):
    try:
        # Sentiment analysis
        llm_key = os.environ.get('EMERGENT_LLM_KEY')
        chat = LlmChat(
            api_key=llm_key,
            session_id=f"sentiment_{uuid.uuid4()}",
            system_message="You are a sentiment analyzer. Respond ONLY with one word: positive, negative, or neutral."
        ).with_model("openai", "gpt-5")
        
        user_message = UserMessage(text=f"Analyze sentiment: {input.text}")
        sentiment = await chat.send_message(user_message)
        sentiment = sentiment.strip().lower()
    except Exception as e:
        logging.error(f"Sentiment analysis failed: {e}")
        sentiment = "neutral"
    
    pulse = MoodPulse(
        user_id=current_user.id,
        emotion=input.emotion,
        text=input.text,
        location=input.location,
        sentiment=sentiment
    )
    
    pulse_dict = pulse.model_dump()
    pulse_dict["timestamp"] = pulse_dict["timestamp"].isoformat()
    await db.mood_pulses.insert_one(pulse_dict)
    
    # Try to match with a circle or create new one
    await match_to_circle(pulse, current_user.id)
    
    return pulse

async def match_to_circle(pulse: MoodPulse, user_id: str):
    # Find active circles with same emotion
    active_circles = await db.circles.find({
        "emotion": pulse.emotion,
        "expires_at": {"$gt": datetime.now(timezone.utc).isoformat()},
        "members": {"$size": {"$lt": 10}}  # Max 10 members
    }).to_list(100)
    
    if active_circles:
        # Join first available circle
        circle = active_circles[0]
        if user_id not in circle["members"]:
            await db.circles.update_one(
                {"id": circle["id"]},
                {"$push": {"members": user_id}}
            )
    else:
        # Create new circle
        new_circle = Circle(
            emotion=pulse.emotion,
            members=[user_id],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        circle_dict = new_circle.model_dump()
        circle_dict["expires_at"] = circle_dict["expires_at"].isoformat()
        circle_dict["created_at"] = circle_dict["created_at"].isoformat()
        await db.circles.insert_one(circle_dict)

@api_router.get("/pulse/me", response_model=List[MoodPulse])
async def get_my_pulses(current_user: User = Depends(get_current_user)):
    pulses = await db.mood_pulses.find(
        {"user_id": current_user.id},
        {"_id": 0}
    ).sort("timestamp", -1).limit(50).to_list(50)
    
    for pulse in pulses:
        if isinstance(pulse.get("timestamp"), str):
            pulse["timestamp"] = datetime.fromisoformat(pulse["timestamp"])
    
    return pulses

# ===== CIRCLE ENDPOINTS =====
@api_router.get("/circles", response_model=List[Circle])
async def get_my_circles(current_user: User = Depends(get_current_user)):
    circles = await db.circles.find(
        {
            "members": current_user.id,
            "expires_at": {"$gt": datetime.now(timezone.utc).isoformat()}
        },
        {"_id": 0}
    ).to_list(100)
    
    for circle in circles:
        if isinstance(circle.get("expires_at"), str):
            circle["expires_at"] = datetime.fromisoformat(circle["expires_at"])
        if isinstance(circle.get("created_at"), str):
            circle["created_at"] = datetime.fromisoformat(circle["created_at"])
    
    return circles

@api_router.get("/circles/{circle_id}", response_model=Circle)
async def get_circle(circle_id: str, current_user: User = Depends(get_current_user)):
    circle = await db.circles.find_one({"id": circle_id}, {"_id": 0})
    
    if not circle:
        raise HTTPException(status_code=404, detail="Circle not found")
    
    if current_user.id not in circle["members"]:
        raise HTTPException(status_code=403, detail="Not a member of this circle")
    
    if isinstance(circle.get("expires_at"), str):
        circle["expires_at"] = datetime.fromisoformat(circle["expires_at"])
    if isinstance(circle.get("created_at"), str):
        circle["created_at"] = datetime.fromisoformat(circle["created_at"])
    
    return Circle(**circle)

@api_router.post("/circles/{circle_id}/messages", response_model=CircleMessage)
async def send_circle_message(circle_id: str, input: CircleMessageInput, current_user: User = Depends(get_current_user)):
    circle = await db.circles.find_one({"id": circle_id})
    
    if not circle:
        raise HTTPException(status_code=404, detail="Circle not found")
    
    if current_user.id not in circle["members"]:
        raise HTTPException(status_code=403, detail="Not a member of this circle")
    
    message = CircleMessage(
        circle_id=circle_id,
        user_id=current_user.id,
        message=input.message
    )
    
    message_dict = message.model_dump()
    message_dict["timestamp"] = message_dict["timestamp"].isoformat()
    await db.circle_messages.insert_one(message_dict)
    
    return message

@api_router.get("/circles/{circle_id}/messages", response_model=List[CircleMessage])
async def get_circle_messages(circle_id: str, current_user: User = Depends(get_current_user)):
    circle = await db.circles.find_one({"id": circle_id})
    
    if not circle:
        raise HTTPException(status_code=404, detail="Circle not found")
    
    if current_user.id not in circle["members"]:
        raise HTTPException(status_code=403, detail="Not a member of this circle")
    
    messages = await db.circle_messages.find(
        {"circle_id": circle_id},
        {"_id": 0}
    ).sort("timestamp", 1).to_list(1000)
    
    for msg in messages:
        if isinstance(msg.get("timestamp"), str):
            msg["timestamp"] = datetime.fromisoformat(msg["timestamp"])
    
    return messages

# ===== EMOTIONAL MAP =====
@api_router.get("/map")
async def get_emotional_map():
    # Aggregate emotions by location
    pipeline = [
        {"$match": {"location": {"$ne": None}}},
        {"$group": {
            "_id": "$location",
            "emotions": {"$push": "$emotion"},
            "count": {"$sum": 1}
        }}
    ]
    
    results = await db.mood_pulses.aggregate(pipeline).to_list(1000)
    
    # Calculate emotion percentages per location
    map_data = []
    for result in results:
        emotions_count = {}
        for emotion in result["emotions"]:
            emotions_count[emotion] = emotions_count.get(emotion, 0) + 1
        
        percentages = {k: round((v/result["count"])*100) for k, v in emotions_count.items()}
        map_data.append({
            "location": result["_id"],
            "total": result["count"],
            "emotions": percentages
        })
    
    return map_data

# ===== VOICE DROPS =====
@api_router.post("/voice-drops", response_model=VoiceDrop)
async def create_voice_drop(input: VoiceDropInput, current_user: User = Depends(get_current_user)):
    voice_drop = VoiceDrop(
        user_id=current_user.id,
        voice_url=input.voice_url,
        emotion=input.emotion
    )
    
    voice_dict = voice_drop.model_dump()
    voice_dict["timestamp"] = voice_dict["timestamp"].isoformat()
    await db.voice_drops.insert_one(voice_dict)
    
    return voice_drop

@api_router.get("/voice-drops", response_model=List[VoiceDrop])
async def get_voice_drops(limit: int = 20):
    drops = await db.voice_drops.find(
        {},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
    for drop in drops:
        if isinstance(drop.get("timestamp"), str):
            drop["timestamp"] = datetime.fromisoformat(drop["timestamp"])
    
    return drops

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()