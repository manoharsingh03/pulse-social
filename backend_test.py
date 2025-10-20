import requests
import sys
import json
from datetime import datetime, timezone, timedelta
import uuid
import subprocess
import time

class PulseAPITester:
    def __init__(self, base_url="https://pulse-social-6.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.session_token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if headers:
            test_headers.update(headers)
            
        if self.session_token and 'Authorization' not in test_headers:
            test_headers['Authorization'] = f'Bearer {self.session_token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                self.failed_tests.append({
                    "test": name,
                    "expected": expected_status,
                    "actual": response.status_code,
                    "endpoint": endpoint
                })
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({
                "test": name,
                "error": str(e),
                "endpoint": endpoint
            })
            return False, {}

    def create_test_user_and_session(self):
        """Create test user and session in MongoDB"""
        print("\n🔧 Creating test user and session...")
        
        user_id = f"test-user-{int(time.time())}"
        session_token = f"test_session_{int(time.time())}"
        email = f"test.user.{int(time.time())}@example.com"
        
        mongo_script = f"""
        use('test_database');
        var userId = '{user_id}';
        var sessionToken = '{session_token}';
        var email = '{email}';
        
        db.users.insertOne({{
          id: userId,
          email: email,
          name: 'Test User',
          picture: 'https://via.placeholder.com/150',
          created_at: new Date()
        }});
        
        db.user_sessions.insertOne({{
          user_id: userId,
          session_token: sessionToken,
          expires_at: new Date(Date.now() + 7*24*60*60*1000),
          created_at: new Date()
        }});
        
        print('User created: ' + userId);
        print('Session token: ' + sessionToken);
        """
        
        try:
            result = subprocess.run(
                ['mongosh', '--eval', mongo_script],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.user_id = user_id
                self.session_token = session_token
                print(f"✅ Test user created: {user_id}")
                print(f"✅ Session token: {session_token}")
                return True
            else:
                print(f"❌ Failed to create test user: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error creating test user: {str(e)}")
            return False

    def cleanup_test_data(self):
        """Clean up test data"""
        print("\n🧹 Cleaning up test data...")
        
        cleanup_script = """
        use('test_database');
        db.users.deleteMany({email: /test\\.user\\./});
        db.user_sessions.deleteMany({session_token: /test_session/});
        db.mood_pulses.deleteMany({user_id: /test-user-/});
        db.circles.deleteMany({members: /test-user-/});
        db.circle_messages.deleteMany({user_id: /test-user-/});
        print('Test data cleaned up');
        """
        
        try:
            subprocess.run(['mongosh', '--eval', cleanup_script], timeout=30)
            print("✅ Test data cleaned up")
        except Exception as e:
            print(f"⚠️ Cleanup warning: {str(e)}")

    def test_auth_flow(self):
        """Test authentication endpoints"""
        print("\n=== TESTING AUTHENTICATION ===")
        
        # Test /auth/me with valid session
        success, user_data = self.run_test(
            "Get current user",
            "GET",
            "auth/me",
            200
        )
        
        if success and user_data:
            print(f"✅ User authenticated: {user_data.get('name', 'Unknown')}")
            return True
        else:
            print("❌ Authentication failed")
            return False

    def test_pulse_creation(self):
        """Test pulse creation and sentiment analysis"""
        print("\n=== TESTING PULSE CREATION ===")
        
        pulse_data = {
            "emotion": "stressed",
            "text": "Feeling overwhelmed with work today",
            "location": "Global"
        }
        
        success, response = self.run_test(
            "Create mood pulse",
            "POST",
            "pulse",
            200,
            data=pulse_data
        )
        
        if success:
            pulse_id = response.get('id')
            sentiment = response.get('sentiment')
            print(f"✅ Pulse created with ID: {pulse_id}")
            print(f"✅ Sentiment analysis: {sentiment}")
            
            # Test getting user's pulses
            success2, pulses = self.run_test(
                "Get my pulses",
                "GET",
                "pulse/me",
                200
            )
            
            if success2 and len(pulses) > 0:
                print(f"✅ Retrieved {len(pulses)} pulses")
                return pulse_id
            
        return None

    def test_circle_functionality(self):
        """Test circle matching and messaging"""
        print("\n=== TESTING CIRCLE FUNCTIONALITY ===")
        
        # Get user's circles
        success, circles = self.run_test(
            "Get my circles",
            "GET",
            "circles",
            200
        )
        
        if success:
            print(f"✅ Retrieved {len(circles)} circles")
            
            if len(circles) > 0:
                circle_id = circles[0]['id']
                print(f"✅ Testing circle: {circle_id}")
                
                # Test getting specific circle
                success2, circle_data = self.run_test(
                    "Get specific circle",
                    "GET",
                    f"circles/{circle_id}",
                    200
                )
                
                if success2:
                    print(f"✅ Circle details retrieved: {circle_data.get('emotion')} emotion")
                    
                    # Test sending message
                    message_data = {"message": "Hello everyone, how are you feeling?"}
                    success3, msg_response = self.run_test(
                        "Send circle message",
                        "POST",
                        f"circles/{circle_id}/messages",
                        200,
                        data=message_data
                    )
                    
                    if success3:
                        print(f"✅ Message sent: {msg_response.get('id')}")
                        
                        # Test getting messages
                        success4, messages = self.run_test(
                            "Get circle messages",
                            "GET",
                            f"circles/{circle_id}/messages",
                            200
                        )
                        
                        if success4:
                            print(f"✅ Retrieved {len(messages)} messages")
                            return True
                            
        return False

    def test_emotional_map(self):
        """Test emotional map endpoint"""
        print("\n=== TESTING EMOTIONAL MAP ===")
        
        success, map_data = self.run_test(
            "Get emotional map",
            "GET",
            "map",
            200
        )
        
        if success:
            print(f"✅ Map data retrieved: {len(map_data)} locations")
            return True
        return False

    def test_voice_drops(self):
        """Test voice drops functionality (mocked)"""
        print("\n=== TESTING VOICE DROPS ===")
        
        # Test creating voice drop
        voice_data = {
            "voice_url": "https://example.com/voice.mp3",
            "emotion": "joyful"
        }
        
        success, response = self.run_test(
            "Create voice drop",
            "POST",
            "voice-drops",
            200,
            data=voice_data
        )
        
        if success:
            print(f"✅ Voice drop created: {response.get('id')}")
            
            # Test getting voice drops
            success2, drops = self.run_test(
                "Get voice drops",
                "GET",
                "voice-drops",
                200
            )
            
            if success2:
                print(f"✅ Retrieved {len(drops)} voice drops")
                return True
                
        return False

    def test_logout(self):
        """Test logout functionality"""
        print("\n=== TESTING LOGOUT ===")
        
        success, response = self.run_test(
            "Logout",
            "POST",
            "auth/logout",
            200
        )
        
        if success:
            print("✅ Logout successful")
            return True
        return False

def main():
    print("🚀 Starting Pulse API Testing...")
    
    tester = PulseAPITester()
    
    # Setup test user and session
    if not tester.create_test_user_and_session():
        print("❌ Failed to create test user. Exiting.")
        return 1
    
    try:
        # Run all tests
        auth_success = tester.test_auth_flow()
        if not auth_success:
            print("❌ Authentication failed. Cannot proceed with other tests.")
            return 1
            
        pulse_id = tester.test_pulse_creation()
        circle_success = tester.test_circle_functionality()
        map_success = tester.test_emotional_map()
        voice_success = tester.test_voice_drops()
        logout_success = tester.test_logout()
        
        # Print results
        print(f"\n📊 FINAL RESULTS:")
        print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
        print(f"Success rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
        
        if tester.failed_tests:
            print(f"\n❌ Failed tests:")
            for failure in tester.failed_tests:
                print(f"  - {failure}")
        
        return 0 if tester.tests_passed == tester.tests_run else 1
        
    finally:
        # Cleanup
        tester.cleanup_test_data()

if __name__ == "__main__":
    sys.exit(main())