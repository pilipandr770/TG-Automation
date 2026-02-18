#!/usr/bin/env python
"""
Comprehensive test of CSRF token handling in forms.
"""
import sys
import os
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(__file__))

def test_csrf_form_submission():
    """Test that CSRF tokens work in form submissions."""
    from app import create_app
    import re
    
    app = create_app()
    client = app.test_client()
    
    print("=" * 60)
    print("CSRF Token Form Submission Test")
    print("=" * 60)
    
    # Step 1: GET login page and extract CSRF token
    print("\n1. Fetching login page...")
    response = client.get('/auth/login')
    print(f"   Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"   ✗ Failed to get login page")
        return False
    
    html = response.get_data(as_text=True)
    
    # Find csrf_token in HTML
    csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if not csrf_match:
        print("   ✗ CSRF token not found in login form")
        print(f"\n   Searching for 'csrf_token' in HTML...")
        if 'csrf_token' in html:
            print("   ✓ 'csrf_token' text found, but not in expected format")
            # Print context around csrf_token
            idx = html.find('csrf_token')
            print(f"   Context: ...{html[max(0, idx-50):idx+100]}...")
        else:
            print("   ✗ No 'csrf_token' found anywhere in HTML")
        return False
    
    csrf_token = csrf_match.group(1)
    print(f"   ✓ Found CSRF token: {csrf_token[:20]}...")
    
    # Step 2: Try POST with CSRF token
    print("\n2. Testing POST submission with CSRF token...")
    print("   Note: This will fail with invalid credentials, but we're checking CSRF validation")
    
    response = client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'wrongpass',
        'csrf_token': csrf_token
    }, follow_redirects=False)
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 400:
        print("   ✗ Got 400 error - CSRF validation failed")
        html = response.get_data(as_text=True)
        if 'csrf' in html.lower():
            print("     Response mentions CSRF error")
        else:
            print("     Response doesn't mention CSRF (different 400 error)")
        return False
    elif response.status_code == 401 or response.status_code == 200:
        print("   ✓ Form was accepted (wrong credentials, but no CSRF error)")
        if 'Invalid username' in response.get_data(as_text=True):
            print("     Server validated form and checked credentials")
        return True
    elif response.status_code == 302:
        print("   ✓ Form was accepted (redirect response)")
        return True
    else:
        print(f"   ? Unexpected status code: {response.status_code}")
        return False

if __name__ == '__main__':
    try:
        success = test_csrf_form_submission()
        print("\n" + "=" * 60)
        if success:
            print("✓ CSRF form submission test PASSED")
            sys.exit(0)
        else:
            print("✗ CSRF form submission test FAILED")
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
