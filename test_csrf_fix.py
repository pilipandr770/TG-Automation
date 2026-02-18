#!/usr/bin/env python
"""
Test CSRF Token Fix
Verifies that CSRF tokens are properly rendered and validated.
"""
import os
import sys
import json
import re
from app import create_app, db
from app.models import User


def test_csrf_token_rendering():
    """Test that CSRF tokens are rendered in templates."""
    app = create_app('development')
    app.config['TESTING'] = True
    app.config['LOGIN_DISABLED'] = False
    
    with app.app_context():
        # Create test user
        db.create_all()
        test_user = User.query.filter_by(username='testuser').first()
        if not test_user:
            test_user = User(username='testuser', email='test@example.com', is_admin=True)
            test_user.set_password('testpass123')
            db.session.add(test_user)
            db.session.commit()
        
        with app.test_client() as client:
            # GET login page first to extract CSRF token
            print("1. Getting login page...")
            response = client.get('/auth/login')
            
            if response.status_code != 200:
                print(f"✗ Failed to get login page: {response.status_code}")
                return False
            
            html_content = response.get_data(as_text=True)
            
            # Extract CSRF token from login page
            login_csrf_tokens = re.findall(
                r'<input[^>]*name=["\']?csrf_token["\']?[^>]*value=["\']([^"\']+)["\'][^>]*>',
                html_content,
                re.IGNORECASE
            )
            
            if not login_csrf_tokens:
                print("✗ No CSRF token found on login page!")
                return False
            
            login_csrf_token = login_csrf_tokens[0]
            print(f"✓ Login page loaded with CSRF token (first 20 chars: {login_csrf_token[:20]}...)")
            
            # Login with CSRF token
            print("\n2. Testing login with CSRF token...")
            response = client.post('/auth/login', data={
                'username': 'testuser',
                'password': 'testpass123',
                'csrf_token': login_csrf_token
            }, follow_redirects=True)
            
            if response.status_code == 200:
                print("✓ Login successful")
            else:
                print(f"✗ Login failed: {response.status_code}")
                return False
            
            # Get instructions page
            print("\n3. Getting instructions page...")
            response = client.get('/admin/instructions', follow_redirects=True)
            
            if response.status_code != 200:
                print(f"✗ Failed to get instructions page: {response.status_code}")
                return False
            
            html_content = response.get_data(as_text=True)
            
            # Extract CSRF tokens from HTML
            csrf_tokens = re.findall(
                r'<input[^>]*name=["\']?csrf_token["\']?[^>]*value=["\']([^"\']+)["\'][^>]*>',
                html_content,
                re.IGNORECASE
            )
            
            print(f"✓ Instructions page loaded (found {len(csrf_tokens)} CSRF token fields)")
            
            if not csrf_tokens:
                print("✗ No CSRF tokens found in HTML!")
                print("  This means the token is not being rendered.")
                # Debug: print part of the HTML to see what's happening
                print("\n  Checking if csrf_token input exists...")
                if 'csrf_token' in html_content:
                    print("  ✓ csrf_token mentioned in HTML")
                    # Find and print the lines with csrf_token
                    for line in html_content.split('\n'):
                        if 'csrf_token' in line:
                            print(f"    {line.strip()[:100]}")
                else:
                    print("  ✗ csrf_token not mentioned anywhere in HTML")
                return False
            
            # Test form submission with CSRF token
            print("\n4. Testing form submission with CSRF token...")
            csrf_token = csrf_tokens[0]
            
            response = client.post('/admin/instructions', data={
                'dm_instruction': 'Test instruction for DM',
                'action': 'save_dm',
                'csrf_token': csrf_token
            }, follow_redirects=True)
            
            if response.status_code == 200:
                print("✓ Form submission accepted (200 OK)")
                
                # Check if success message is in the response
                if 'DM instruction saved' in response.get_data(as_text=True):
                    print("✓ Success message found in response")
                    return True
                else:
                    print("⚠ Form accepted but success message not found")
                    return True
            elif response.status_code == 400:
                print(f"✗ Form submission rejected with 400 error")
                error_data = response.get_data(as_text=True)
                if 'CSRF' in error_data:
                    print("  Error: CSRF validation failed")
                print(f"  Response: {error_data[:200]}")
                return False
            else:
                print(f"✗ Unexpected status code: {response.status_code}")
                return False


if __name__ == '__main__':
    print("=" * 70)
    print("CSRF TOKEN FIX TEST")
    print("=" * 70)
    
    try:
        success = test_csrf_token_rendering()
        
        print("\n" + "=" * 70)
        if success:
            print("✓ CSRF TOKEN FIX TEST PASSED")
            print("=" * 70)
            sys.exit(0)
        else:
            print("✗ CSRF TOKEN FIX TEST FAILED")
            print("=" * 70)
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
