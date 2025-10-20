import subprocess
import requests
import time
from datetime import datetime, timezone, timedelta

# Create test user and session
user_id = f"debug-user-{int(time.time())}"
session_token = f"debug_session_{int(time.time())}"
email = f"debug.user.{int(time.time())}@example.com"

print(f"Creating user: {user_id}")
print(f"Session token: {session_token}")

# Create with proper date format
mongo_script = f"""
use('test_database');
var userId = '{user_id}';
var sessionToken = '{session_token}';
var email = '{email}';

// Create user
db.users.insertOne({{
  id: userId,
  email: email,
  name: 'Debug User',
  picture: 'https://via.placeholder.com/150',
  created_at: new Date().toISOString()
}});

// Create session with future expiry
var expiryDate = new Date(Date.now() + 7*24*60*60*1000);
db.user_sessions.insertOne({{
  user_id: userId,
  session_token: sessionToken,
  expires_at: expiryDate.toISOString(),
  created_at: new Date().toISOString()
}});

print('User created: ' + userId);
print('Session expires at: ' + expiryDate.toISOString());
"""

try:
    result = subprocess.run(['mongosh', '--eval', mongo_script], capture_output=True, text=True, timeout=30)
    print("MongoDB result:", result.stdout)
    if result.stderr:
        print("MongoDB error:", result.stderr)
    
    # Now test the API
    print(f"\nTesting API with session token: {session_token}")
    
    response = requests.get(
        "https://pulse-social-6.preview.emergentagent.com/api/auth/me",
        headers={"Authorization": f"Bearer {session_token}"},
        timeout=10
    )
    
    print(f"API Response Status: {response.status_code}")
    print(f"API Response: {response.text}")
    
    # Check what's actually in the database
    check_script = f"""
    use('test_database');
    var session = db.user_sessions.findOne({{session_token: '{session_token}'}});
    if (session) {{
        print('Session found:');
        print('User ID: ' + session.user_id);
        print('Expires at: ' + session.expires_at);
        print('Expires at type: ' + typeof session.expires_at);
        print('Current time: ' + new Date().toISOString());
        print('Is expired: ' + (new Date(session.expires_at) < new Date()));
    }} else {{
        print('Session not found');
    }}
    
    var user = db.users.findOne({{id: '{user_id}'}});
    if (user) {{
        print('User found: ' + user.name);
    }} else {{
        print('User not found');
    }}
    """
    
    check_result = subprocess.run(['mongosh', '--eval', check_script], capture_output=True, text=True, timeout=30)
    print("\nDatabase check:", check_result.stdout)
    
except Exception as e:
    print(f"Error: {e}")

# Cleanup
cleanup_script = f"""
use('test_database');
db.users.deleteOne({{id: '{user_id}'}});
db.user_sessions.deleteOne({{session_token: '{session_token}'}});
print('Cleaned up debug data');
"""

try:
    subprocess.run(['mongosh', '--eval', cleanup_script], timeout=30)
    print("Cleanup completed")
except:
    pass