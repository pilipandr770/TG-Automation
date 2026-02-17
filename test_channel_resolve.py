#!/usr/bin/env python
"""Test channel resolution and joining"""
from dotenv import load_dotenv
load_dotenv()

import asyncio
from app import create_app
from app.services.telegram_client import TelegramClientManager
from app.models import DiscoveredChannel

app = create_app()

async def test():
    with app.app_context():
        client_mgr = TelegramClientManager()
        client = await client_mgr.get_client()
        
        if not client:
            print("[ERROR] No client")
            return
        
        # Try to find and join online_crypto_bonuses
        channel_username = "online_crypto_bonuses"
        print(f"[1] Checking channel: {channel_username}")
        
        # Check if already in discovered channels
        channel = DiscoveredChannel.query.filter_by(username=channel_username).first()
        if channel:
            print(f"   Found in DB: telegram_id={channel.telegram_id}, type={channel.channel_type}")
            print(f"   Is_joined: {channel.is_joined}")
            print(f"   Channel type: {channel.channel_type}")
            
            # Try to use telegram_id if available
            if channel.telegram_id:
                print(f"\n[2] Trying to message using telegram_id: {channel.telegram_id}")
                try:
                    # For channels, telegram_id needs to be negative
                    channel_id = channel.telegram_id
                    if channel.channel_type in ['channel', 'supergroup'] and channel_id > 0:
                        channel_id = -channel_id
                    print(f"   Using ID: {channel_id}")
                    message = await client.send_message(channel_id, "Test message from telegram_id")
                    print(f"   SUCCESS! Message ID: {message.id}")
                    return
                except Exception as e:
                    print(f"   FAILED: {e}")
        
        # Try with @-prefixed username
        print(f"\n[3] Trying with @-prefixed username: @{channel_username}")
        try:
            message = await client.send_message(f"@{channel_username}", "Test with @")
            print(f"   SUCCESS! Message ID: {message.id}")
            return
        except Exception as e:
            print(f"   FAILED: {e}")
        
        # Try to get entity by username first
        print(f"\n[4] Trying to resolve via GetChannelRequest")
        try:
            # Try to get the channel
            from telethon.tl.functions.channels import GetByUsernameRequest
            entity = await client.get_entity(channel_username)
            print(f"   Resolved entity: {entity}")
            
            print(f"\n[5] Trying to message resolved entity")
            message = await client.send_message(entity, "Test with resolved entity")
            print(f"   SUCCESS! Message ID: {message.id}")
        except Exception as e:
            print(f"   FAILED: {e}")

asyncio.run(test())
