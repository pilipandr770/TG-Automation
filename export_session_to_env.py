#!/usr/bin/env python
"""Export current Telegram session to .env file."""
import os
from app import create_app, db
from app.models import TelegramSession
from dotenv import load_dotenv

app = create_app()

with app.app_context():
    print("=" * 70)
    print("💾 EXPORTING TELEGRAM SESSION TO .ENV")
    print("=" * 70)
    
    # Get the active session
    session = TelegramSession.query.filter_by(session_name='default', is_active=True).first()
    
    if not session or not session.session_string:
        print("\n❌ ERROR: No active session found")
        print("   Run: python reauthenticate.py")
        exit(1)
    
    print(f"\n✅ Found active session")
    print(f"   Session string: {session.session_string[:50]}...")
    print(f"   Length: {len(session.session_string)} chars")
    
    # Read current .env
    env_file = '.env'
    with open(env_file, 'r', encoding='utf-8') as f:
        env_content = f.read()
    
    # Check if TELEGRAM_SESSION_STRING already exists
    if 'TELEGRAM_SESSION_STRING=' in env_content:
        print(f"\n⚠️  TELEGRAM_SESSION_STRING already exists in .env")
        print(f"   Updating it...")
        # Replace existing
        lines = env_content.split('\n')
        new_lines = []
        for line in lines:
            if line.startswith('TELEGRAM_SESSION_STRING='):
                new_lines.append(f'TELEGRAM_SESSION_STRING={session.session_string}')
            else:
                new_lines.append(line)
        env_content = '\n'.join(new_lines)
    else:
        print(f"\n➕ Adding TELEGRAM_SESSION_STRING to .env")
        # Add after TELEGRAM_PHONE
        lines = env_content.split('\n')
        new_lines = []
        for i, line in enumerate(lines):
            new_lines.append(line)
            if line.startswith('TELEGRAM_PHONE='):
                new_lines.append(f'TELEGRAM_SESSION_STRING={session.session_string}')
        env_content = '\n'.join(new_lines)
    
    # Write back
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print(f"✅ Saved to .env file")
    
    print("\n" + "=" * 70)
    print("📝 TELEGRAM_SESSION_STRING is now in .env")
    print("=" * 70)
    print(f"\nFormat: TELEGRAM_SESSION_STRING={session.session_string[:30]}...")
    print(f"\nNext restart:")
    print(f"  1. System will load session from .env automatically")
    print(f"  2. No re-authentication needed")
    print(f"  3. Publisher will work immediately")
    print("\n" + "=" * 70)
