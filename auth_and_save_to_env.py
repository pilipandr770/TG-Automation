#!/usr/bin/env python
"""
Complete workflow to authenticate and save Telegram session to .env
"""
import asyncio
import os
from app import create_app, db
from app.models import TelegramSession
from app.services.telegram_client import TelegramClientManager
from dotenv import load_dotenv

async def complete_authentication_workflow():
    app = create_app()
    
    with app.app_context():
        print("=" * 70)
        print("🔐 COMPLETE AUTHENTICATION & SAVE WORKFLOW")
        print("=" * 70)
        
        # Step 1: Check if we need to authenticate
        print("\n[STEP 1] Checking current session...")
        old_session = TelegramSession.query.filter_by(session_name='default', is_active=True).first()
        
        if old_session and old_session.session_string and len(old_session.session_string) > 100:
            print(f"  ✅ Found valid session in database")
            print(f"  Created: {old_session.created_at}")
        else:
            print(f"  ⚠️  No valid session, will authenticate...")
            
            # Step 1b: Authenticate
            print("\n[STEP 1B] Authenticating with Telegram...")
            
            client_mgr = TelegramClientManager()
            
            # Clear old session
            if old_session:
                old_session.is_active = False
                db.session.commit()
            
            try:
                client = await client_mgr.get_client()
                print(f"  Client created")
                
                await client.connect()
                print(f"  ✅ Connected to Telegram")
                
                # Get credentials
                api_id = os.getenv('TELEGRAM_API_ID')
                api_hash = os.getenv('TELEGRAM_API_HASH')
                phone = os.getenv('TELEGRAM_PHONE')
                
                print(f"  Starting authentication...")
                await client.start(phone=phone)
                print(f"  ✅ Authentication successful!")
                
                # Save to database
                client_mgr.save_session_to_db()
                print(f"  ✅ Session saved to database")
                
                await client.disconnect()
                
            except Exception as e:
                print(f"  ❌ Authentication failed: {e}")
                return False
        
        # Step 2: Load from database and prepare to save
        print("\n[STEP 2] Preparing to export session...")
        
        session = TelegramSession.query.filter_by(session_name='default', is_active=True).first()
        
        if not session or not session.session_string:
            print("  ❌ ERROR: No active session found after authentication")
            return False
        
        print(f"  ✅ Session ready for export")
        print(f"  Session length: {len(session.session_string)} chars")
        
        # Step 3: Save to .env
        print("\n[STEP 3] Saving session to .env...")
        
        env_file = '.env'
        with open(env_file, 'r', encoding='utf-8') as f:
            env_content = f.read()
        
        # Replace or add TELEGRAM_SESSION_STRING
        if 'TELEGRAM_SESSION_STRING=' in env_content:
            print(f"  Updating existing TELEGRAM_SESSION_STRING")
            lines = env_content.split('\n')
            new_lines = []
            for line in lines:
                if line.startswith('TELEGRAM_SESSION_STRING='):
                    new_lines.append(f'TELEGRAM_SESSION_STRING={session.session_string}')
                else:
                    new_lines.append(line)
            env_content = '\n'.join(new_lines)
        else:
            print(f"  Adding new TELEGRAM_SESSION_STRING")
            lines = env_content.split('\n')
            new_lines = []
            for i, line in enumerate(lines):
                new_lines.append(line)
                if line.startswith('TELEGRAM_PHONE='):
                    new_lines.append(f'TELEGRAM_SESSION_STRING={session.session_string}')
            env_content = '\n'.join(new_lines)
        
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        print(f"  ✅ Saved to .env file")
        
        print("\n" + "=" * 70)
        print("✅ SUCCESS! SESSION SAVED TO .ENV")
        print("=" * 70)
        
        print(f"""
Next steps:
  1. ✅ Session is now saved in .env (TELEGRAM_SESSION_STRING)
  2. ✅ No more re-authentication needed
  3. Run the system normally:
  
     # Terminal 1 - Flask Admin Panel
     python wsgi.py
     
     # Terminal 2 - Telethon Worker (Discovery + Audience + Publisher)
     python telethon_runner.py

System will automatically load the session from .env and work immediately!
""")
        
        print("=" * 70)
        return True

if __name__ == '__main__':
    asyncio.run(complete_authentication_workflow())
