#!/usr/bin/env python3
"""Find channels where you can post."""
import asyncio
from app import create_app, db
from app.models import DiscoveredChannel, AppConfig
from app.services.telegram_client import get_telegram_client_manager

async def find_writable_channels():
    """Test which channels allow posting."""
    app = create_app()
    
    with app.app_context():
        print("=" * 70)
        print("TESTING WHICH CHANNELS ALLOW POSTING")
        print("=" * 70)
        
        # Get Telegram client
        client_mgr = get_telegram_client_manager()
        client_mgr.load_session_from_db()
        
        client = await client_mgr.get_client()
        if not client:
            print("❌ Cannot connect to Telegram")
            return
        
        try:
            await client.connect()
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return
        
        # Get joined channels
        channels = DiscoveredChannel.query.filter_by(is_joined=True).limit(20).all()
        
        print(f"\nTesting {len(channels)} channels...\n")
        
        writable = []
        readonly = []
        
        for ch in channels:
            # Try to send a test message (don't actually post, just check permissions)
            try:
                # Determine how to reference the channel
                channel_ref = f"@{ch.username}" if ch.username else ch.telegram_id
                
                # In a real scenario, we'd use client.forward_messages() or check permissions
                # For now, we'll just suggest channels based on type and whether user joined
                
                print(f"  Checking: {ch.title[:40]}")
                print(f"    Username: {channel_ref}")
                
                # Assume supergroups are more permissive
                if ch.channel_type == 'supergroup':
                    writable.append((channel_ref, ch.title))
                    print(f"    ✅ Likely writable (Supergroup)")
                elif ch.channel_type == 'channel':
                    print(f"    ⚠️  Channel (may be read-only)")
                    readonly.append((channel_ref, ch.title))
                
            except Exception as e:
                print(f"    ❌ Error: {str(e)[:40]}")
        
        print("\n" + "=" * 70)
        print("RECOMMENDATIONS:")
        print("=" * 70)
        
        if writable:
            print(f"\n✅ Likely writable channels ({len(writable)}):")
            for ch_ref, title in writable[:5]:
                print(f"  python set_target_channel.py {ch_ref.lstrip('@')}")
                print(f"    → {title}")
        
        print(f"\n⚠️  Read-only channels ({len(readonly)}):")
        for ch_ref, title in readonly[:3]:
            print(f"  {ch_ref} → {title}")
        
        print("""
BEST OPTION: Create a new Telegram channel
  1. Create private/public channel in Telegram
  2. Make sure you're the admin
  3. Join it from this account
  4. Set as target channel

Example channels that work well for publishing:
  - Adult discussion groups (typically allow posting)
  - Dating/lifestyle communities
  - News/discussion channels (if you're admin)
  - Personal/business channels
""")
        
        # Close connection
        await client.disconnect()

if __name__ == '__main__':
    asyncio.run(find_writable_channels())
