#!/usr/bin/env python
"""
Debug CSRF Token Rendering
Shows what's in the HTML to debug token rendering
"""
import os
import sys
import re
from app import create_app, db
from app.models import User


def debug_csrf_rendering():
    """Debug CSRF token rendering."""
    app = create_app('development')
    app.config['TESTING'] = True
    
    with app.app_context():
        db.create_all()
        # Create test user if doesn't exist
        test_user = User.query.filter_by(username='testuser').first()
        if not test_user:
            test_user = User(username='testuser', email='test@example.com', is_admin=True)
            test_user.set_password('testpass123')
            db.session.add(test_user)
            db.session.commit()
        
        with app.test_client() as client:
            # Get login page
            print("Getting login page...")
            response = client.get('/auth/login')
            
            html = response.get_data(as_text=True)
            print(f"Status: {response.status_code}")
            print(f"HTML length: {len(html)}")
            
            # Find lines with csrf_token
            print("\nLines containing 'csrf_token':")
            for i, line in enumerate(html.split('\n'), 1):
                if 'csrf_token' in line.lower():
                    print(f"  Line {i}: {line.strip()}")
            
            # Extract the csrf_token input
            token_inputs = re.findall(
                r'<input[^>]*name=["\']?csrf_token["\']?[^>]*>',
                html,
                re.IGNORECASE
            )
            print(f"\nFound {len(token_inputs)} csrf_token input fields:")
            for inp in token_inputs:
                print(f"  {inp}")
            
            # Extract the value
            values = re.findall(
                r'<input[^>]*name=["\']?csrf_token["\']?[^>]*value=["\']([^"\']*)["\']',
                html,
                re.IGNORECASE
            )
            print(f"\nExtracted values: {values}")
            
            # Look for the form itself
            forms = re.findall(r'<form[^>]*>.*?</form>', html, re.DOTALL)
            print(f"\nFound {len(forms)} forms")
            if forms:
                first_form = forms[0][:500]
                print(f"First form (first 500 chars):\n{first_form}")


if __name__ == '__main__':
    try:
        debug_csrf_rendering()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
