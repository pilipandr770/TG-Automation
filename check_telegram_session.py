#!/usr/bin/env python
"""Check Telegram session status."""
from app import create_app, db
from app.models import TelegramSession

app = create_app()

with app.app_context():
    print("=" * 70)
    print("🔐 TELEGRAM SESSION STATUS")
    print("=" * 70)
    
    session = TelegramSession.query.filter_by(session_name='default', is_active=True).first()
    
    if not session:
        print("\n❌ NO ACTIVE SESSION FOUND")
        # List all sessions
        all_sessions = TelegramSession.query.all()
        if all_sessions:
            print(f"\nFound {len(all_sessions)} session(s) in database:")
            for s in all_sessions:
                print(f"  - {s.session_name}: active={s.is_active}, created={s.created_at}")
        else:
            print("\n❌ NO SESSIONS IN DATABASE AT ALL")
            print("\nNeed to authenticate first!")
        
    else:
        print(f"\n✅ ACTIVE SESSION FOUND")
        print(f"   Session Name: {session.session_name}")
        print(f"   Active: {session.is_active}")
        print(f"   API ID: {session.api_id}")
        print(f"   API Hash: {session.api_hash[:10]}...")
        print(f"   Phone: {session.phone_number}")
        print(f"   Session String Length: {len(session.session_string) if session.session_string else 0}")
        print(f"   Created: {session.created_at}")
        print(f"   Last Connected: {session.last_connected}")
        
        if not session.session_string:
            print("\n⚠️  Session string is empty!")
        else:
            print(f"\n✅ Session string exists and is {len(session.session_string)} bytes")
    
    print("\n" + "=" * 70)
