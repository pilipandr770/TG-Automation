#!/usr/bin/env python
"""
Quick test to verify CSRF token is available in templates.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

def test_csrf_token_in_template():
    """Test that CSRF token is rendered in templates."""
    from app import create_app
    
    app = create_app()
    
    # Create a test client
    client = app.test_client()
    
    print("Testing CSRF token availability...")
    
    # Test the login page (should have CSRF token, doesn't require auth)
    print("\n1. Testing LOGIN page...")
    response = client.get('/auth/login')
    
    if response.status_code == 200:
        html_content = response.get_data(as_text=True)
        
        if 'name="csrf_token"' in html_content and 'value=' in html_content:
            print("✓ CSRF token field found in login form")
            return True
        else:
            print("✗ CSRF token not found in login form")
            print("Checking if context processor is working...")
            if '{{ csrf_token()' in html_content or '{{ csrf_token }}' in html_content:
                print("  Note: csrf_token variable found but not evaluated (context processor may not be working)")
            return False
    else:
        print(f"✗ Unexpected status code: {response.status_code}")
        return False

if __name__ == '__main__':
    try:
        success = test_csrf_token_in_template()
        if success:
            print("\n✓ CSRF token test passed!")
            sys.exit(0)
        else:
            print("\n✗ CSRF token test failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
