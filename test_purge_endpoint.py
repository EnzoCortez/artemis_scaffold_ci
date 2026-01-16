
import os
import sys
import django
from django.test import Client
from django.contrib.auth import get_user_model

# Setup Django configuration
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artemis_project.settings')
django.setup()

User = get_user_model()

from django.test import override_settings

@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
def test_purge_endpoint():
    # 1. Create a test user
    username = 'test_admin'
    password = 'test_password'
    email = 'test@example.com'
    
    try:
        user = User.objects.get(username=username)
        user.set_password(password)
        user.save()
        print(f"User {username} updated.")
    except User.DoesNotExist:
        user = User.objects.create_user(username=username, email=email, password=password)
        print(f"User {username} created.")

    # 2. Initialize Client and Login
    c = Client()
    login_success = c.login(username=username, password=password)
    
    if not login_success:
        print("ERROR: Login failed.")
        return

    print("Login successful.")

    # 3. Test GET (Expected 405)
    print("\nTesting GET /api/purge/ (Expect 405)...")
    response_get = c.get('/api/purge/')
    print(f"GET Status Code: {response_get.status_code}")
    
    # 4. Test POST Dry Run (Expected 200)
    print("\nTesting POST /api/purge/ with dry_run=True (Expect 200)...")
    response_post = c.post('/api/purge/', {'dry_run': True}, content_type='application/json')
    print(f"POST Status Code: {response_post.status_code}")
    print(f"Response Content (Head): {response_post.content[:500]}")

    if response_post.status_code == 200:
        print("\nSUCCESS: Endpoint is working efficiently with POST.")
    else:
        print("\nFAILURE: Endpoint rejected POST.")

if __name__ == '__main__':
    test_purge_endpoint()
