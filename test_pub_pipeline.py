#!/usr/bin/env python
"""Test the full publishing pipeline."""
import asyncio
import os
from app import create_app, db
from app.models import AppConfig, PublishedPost
from app.services.telegram_client import get_telegram_client_manager
from app.services.openai_service import get_openai_service
from app.services.content_fetcher import ContentFetcher
from app.services.publisher_service import PublisherService

async def test_publishing():
    app = create_app()
    
    with app.app_context():
        print("=" * 70)
        print("🧪 FULL PUBLISHING PIPELINE TEST")
        print("=" * 70)
        
        # Step 1: Check configuration
        print("\n[STEP 1] Checking configuration...")
        target_channel = AppConfig.get('target_channel')
        print(f"  Target Channel: {target_channel}")
        
        if not target_channel:
            print("  ❌ ERROR: No target channel configured")
            return
        
        # Step 2: Check Telegram client
        print("\n[STEP 2] Checking Telegram client...")
        client_mgr = get_telegram_client_manager()
        
        # Try to load session from database
        session_loaded = client_mgr.load_session_from_db()
        print(f"  Session loaded: {session_loaded}")
        
        try:
            client = await client_mgr.get_client()
            print(f"  Client created: {client is not None}")
            
            if client:
                # Try to connect
                if not client.is_connected():
                    print("  Attempting to connect...")
                    try:
                        await client.connect()
                        print("  ✅ Connected to Telegram")
                    except Exception as e:
                        print(f"  ❌ Connection failed: {e}")
                        return
                else:
                    print("  ✅ Already connected to Telegram")
                
                # Try to get me
                try:
                    me = await client.get_me()
                    print(f"  ✅ Authenticated as: {me.first_name if me else 'N/A'}")
                except Exception as e:
                    print(f"  ❌ Cannot get me: {e}")
                    return
                
        except Exception as e:
            print(f"  ❌ Client error: {e}")
            return
        
        # Step 3: Check OpenAI
        print("\n[STEP 3] Checking OpenAI service...")
        openai = get_openai_service()
        print(f"  OpenAI service: {openai is not None}")
        print(f"  OpenAI API key: {'✅' if os.getenv('OPENAI_API_KEY') else '❌'}")
        
        # Step 4: Create a test message
        print("\n[STEP 4] Creating test message...")
        test_message = """🚀 **Test Post from Publisher**

This is a test message to verify the publishing pipeline is working correctly.

✨ Features verified:
- ✅ RSS fetching
- ✅ OpenAI rewriting
- ✅ Telegram publishing

⏰ Time: 2026-02-17 20:00:00
🎯 Target audience: Crypto & Tech enthusiasts

🔗 Start conversations with interested users!
"""
        print(f"  Message created ({len(test_message)} chars)")
        
        # Step 5: Try to publish the test message
        print(f"\n[STEP 5] Publishing to {target_channel}...")
        try:
            message = await client.send_message(target_channel, test_message)
            print(f"  ✅ Message sent!")
            print(f"  Message ID: {message.id}")
            print(f"  Message date: {message.date}")
            
            # Save to database
            post = PublishedPost(
                source_url='test://publishing-test',
                source_title='Test Publishing Pipeline',
                original_content=test_message,
                rewritten_content=test_message,
                telegram_message_id=message.id,
                telegram_channel=target_channel,
                status='published',
                published_at=datetime.utcnow(),
                tokens_used=0
            )
            db.session.add(post)
            db.session.commit()
            print(f"  ✅ Saved to database (ID: {post.id})")
            
        except Exception as e:
            print(f"  ❌ Publishing failed: {e}")
            print(f"  Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
        
        # Step 6: Check recent posts
        print("\n[STEP 6] Recent published posts:")
        recent_posts = PublishedPost.query.order_by(PublishedPost.created_at.desc()).limit(5).all()
        for post in recent_posts:
            status_icon = "✅" if post.status == 'published' else "❌" if post.status == 'failed' else "⏳"
            title = post.source_title[:40] if post.source_title else "Unknown"
            print(f"  {status_icon} [{post.status}] {title}")
        
        print("\n" + "=" * 70)
        
        # Finally, disconnect
        if client and client.is_connected():
            await client.disconnect()

if __name__ == '__main__':
    from datetime import datetime
    asyncio.run(test_publishing())
