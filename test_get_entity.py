#!/usr/bin/env python
"""Test getting channel entity from Telethon cache"""
from dotenv import load_dotenv
load_dotenv()

import asyncio
from app import create_app
from app.services.telegram_client import TelegramClientManager

app = create_app()

async def test():
    with app.app_context():
        client_mgr = TelegramClientManager()
        client = await client_mgr.get_client()
        
        if not client:
            print("[ERROR] No client")
            return
        
        channel_username = "online_crypto_bonuses"
        
        # List all chats to see what we have
        print("[1] Getting all dialogs...")
        dialogs = await client.get_dialogs()
        print(f"   Found {len(dialogs)} dialogs")
        
        for dialog in dialogs:
            chat = dialog.entity
            if hasattr(chat, 'username') and chat.username == channel_username:
                print(f"\n   FOUND: {channel_username}")
                print(f"   Type: {type(chat)}")
                print(f"   Obj: {chat}")
                
                print(f"\n[2] Trying to message this entity...")
                try:
                    message = await client.send_message(chat, "Test message!")
                    print(f"   SUCCESS! Message ID: {message.id}")
                    return
                except Exception as e:
                    print(f"   FAILED: {e}")
                    import traceback
                    traceback.print_exc()
                break
        else:
            print(f"   {channel_username} NOT found in dialogs")
            print(f"\n[3] Searching for channel manually...")
            try:
                # Try to search using get_entity
                entity = await client.get_entity(channel_username)
                print(f"   Found via get_entity: {entity}")
                print(f"   Type: {type(entity)}")
                
                print(f"\n[4] Trying to message...")
                message = await client.send_message(entity, "Test!")
                print(f"   SUCCESS! Message ID: {message.id}")
            except Exception as e:
                print(f"   FAILED: {e}")

asyncio.run(test())
