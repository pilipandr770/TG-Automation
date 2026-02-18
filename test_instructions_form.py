#!/usr/bin/env python
"""
Test the instructions form specifically to ensure CSRF tokens work properly.
"""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(__file__))

def test_instructions_form():
    """Test that the instructions form works with CSRF protection."""
    from app import create_app
    from app.models import User
    from werkzeug.security import generate_password_hash
    from app import db
    
    app = create_app()
    client = app.test_client()
    
    print("=" * 70)
    print("Instructions Form CSRF Test")
    print("=" * 70)
    
    # Create test user
    with app.app_context():
        db.create_all()
        
        # Clear any existing test user
        existing = User.query.filter_by(username='test_admin').first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
        
        # Create new test user
        test_user = User(
            username='test_admin',
            email='test_admin@test.com',
            password_hash=generate_password_hash('testpass123'),
            is_admin=True
        )
        db.session.add(test_user)
        db.session.commit()
        print("✓ Created test admin user")
    
    # Login
    print("\n1. Logging in...")
    response = client.post('/auth/login', data={
        'username': 'test_admin',
        'password': 'testpass123',
        'csrf_token': ''  # Will be filled by test client
    })
    
    # For initial login, we need to get CSRF token first
    login_page = client.get('/auth/login')
    csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page.get_data(as_text=True))
    if not csrf_match:
        print("   ✗ Could not find CSRF token on login page")
        return False
    
    csrf_token = csrf_match.group(1)
    
    # Now login with proper CSRF token
    response = client.post('/auth/login', data={
        'username': 'test_admin',
        'password': 'testpass123',
        'csrf_token': csrf_token
    }, follow_redirects=True)
    
    if response.status_code == 200:
        print("   ✓ Logged in successfully")
    else:
        print(f"   ✗ Login failed with status {response.status_code}")
        return False
    
    # Get instructions page
    print("\n2. Accessing instructions page...")
    response = client.get('/admin/instructions')
    
    if response.status_code != 200:
        print(f"   ✗ Failed to get instructions page (status: {response.status_code})")
        return False
    
    html = response.get_data(as_text=True)
    print("   ✓ Instructions page loaded")
    
    # Check for CSRF tokens in forms
    csrf_count = html.count('name="csrf_token"')
    print(f"   ✓ Found {csrf_count} CSRF token fields in page")
    
    if csrf_count < 2:
        print("   ✗ Expected at least 2 CSRF token fields (DM and Channel forms)")
        return False
    
    # Extract CSRF tokens from both forms
    csrf_matches = re.findall(r'name="csrf_token"\s+value="([^"]+)"', html)
    if not csrf_matches:
        print("   ✗ Could not extract CSRF tokens from forms")
        return False
    
    dm_csrf = csrf_matches[0]
    channel_csrf = csrf_matches[1] if len(csrf_matches) > 1 else dm_csrf
    
    print(f"   ✓ DM form CSRF token: {dm_csrf[:20]}...")
    print(f"   ✓ Channel form CSRF token: {channel_csrf[:20]}...")
    
    # Test DM instruction save
    print("\n3. Testing DM instruction form submission...")
    
    test_instruction = "Test instruction for DM: Be helpful and friendly!"
    response = client.post('/admin/instructions', data={
        'dm_instruction': test_instruction,
        'channel_instruction': '',
        'action': 'save_dm',
        'csrf_token': dm_csrf
    }, follow_redirects=False)
    
    print(f"   Response status: {response.status_code}")
    
    if response.status_code == 400:
        print("   ✗ Got 400 error - CSRF validation failed!")
        print("     This means the CSRF token was rejected")
        return False
    elif response.status_code in [200, 302]:
        print("   ✓ Form was accepted without CSRF error")
        
        # Check if redirect contains success message
        if response.status_code == 302:
            redirect_page = client.get(response.location)
            if 'saved successfully' in redirect_page.get_data(as_text=True):
                print("   ✓ Instruction was saved successfully")
        
        return True
    else:
        print(f"   ? Unexpected status code: {response.status_code}")
        return False

if __name__ == '__main__':
    try:
        success = test_instructions_form()
        print("\n" + "=" * 70)
        if success:
            print("✓✓✓ Instructions form CSRF test PASSED ✓✓✓")
            print("\nThe instructions form now works without CSRF errors!")
            sys.exit(0)
        else:
            print("✗✗✗ Instructions form CSRF test FAILED ✗✗✗")
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
