#!/usr/bin/env python
"""Re-authenticate Telegram session."""
import asyncio
from app import create_app, db
from app.models import TelegramSession
from app.services.telegram_client import TelegramClientManager
import os

async def reauthenticate_telegram():
    app = create_app()
    
    with app.app_context():
        print("=" * 70)
        print("🔐 TELEGRAM RE-AUTHENTICATION")
        print("=" * 70)
        
        # Step 1: Clear old session
        print("\n[STEP 1] Clearing old invalid session...")
        old_session = TelegramSession.query.filter_by(session_name='default').first()
        if old_session:
            print(f"  Found old session, marking as inactive...")
            old_session.is_active = False
            db.session.commit()
            print(f"  ✅ Old session marked inactive")
        else:
            print(f"  No previous session found")
        
        # Step 2: Get credentials
        print("\n[STEP 2] Checking Telegram credentials...")
        api_id = os.getenv('TELEGRAM_API_ID')
        api_hash = os.getenv('TELEGRAM_API_HASH')
        phone = os.getenv('TELEGRAM_PHONE')
        
        if not api_id or not api_hash or not phone:
            print("  ❌ Missing required credentials in .env file")
            print("     - TELEGRAM_API_ID")
            print("     - TELEGRAM_API_HASH")
            print("     - TELEGRAM_PHONE")
            return
        
        print(f"  ✅ Credentials found")
        print(f"     API ID: {api_id}")
        print(f"     Phone: {phone}")
        
        # Step 3: Create new session
        print("\n[STEP 3] Creating new Telegram session...")
        client_mgr = TelegramClientManager()
        
        try:
            client = await client_mgr.get_client()
            print(f"  Client created")
            
            # Connect
            print(f"  Attempting to connect...")
            await client.connect()
            print(f"  ✅ Connected to Telegram")
            
            # Start
            print(f"  Attempting to authenticate...")
            await client.start(phone=phone)
            print(f"  ✅ Session created successfully!")
            
            # Save to database
            print(f"  Saving session to database...")
            client_mgr.save_session_to_db()
            print(f"  ✅ Session saved")
            
            # Test it works
            print(f"  Testing authentication...")
            me = await client.get_me()
            print(f"  ✅ Authentication successful!")
            print(f"     User: {me.first_name} {me.last_name or ''}".strip())
            print(f"     Username: @{me.username}")
            
            await client.disconnect()
            print(f"\n✅ RE-AUTHENTICATION COMPLETE!")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return
        
        print("\n" + "=" * 70)
        print("Next: Run the system normally")
        print("=" * 70)

if __name__ == '__main__':
    asyncio.run(reauthenticate_telegram())
