#!/usr/bin/env python
"""Test full publishing cycle"""
from dotenv import load_dotenv
load_dotenv()

import asyncio
from app import create_app
from app.services.publisher_service import PublisherService
from app.services.openai_service import OpenAIService
from app.services.content_fetcher import ContentFetcher
from app.services.telegram_client import TelegramClientManager
from app.models import AppConfig, ContentSource

app = create_app()

async def test():
    with app.app_context():
        # Get config
        target_channel = AppConfig.get('target_channel')
        print(f"Target channel: {target_channel}")
        
        # Initialize services
        client_mgr = TelegramClientManager()
        pub = PublisherService(client_mgr, OpenAIService(), ContentFetcher())
        
        # Fetch content
        print("\n[1] Fetching content...")
        sources = ContentSource.query.filter_by(active=True).all()
        if sources:
            # Reset last_fetched to force fetch
            source = sources[0]
            print(f"   From: {source.name}")
            source.last_fetched = None
            from app import db
            db.session.commit()
            
            items = await pub.fetch_new_content()
            print(f"   Got {len(items)} items")
            
            if items:
                item = items[0]
                print(f"\n[2] Rewriting...")
                print(f"   Title: {item['title'][:60]}")
                rewritten, tokens = await pub.rewrite_content(item, 'en')
                
                if rewritten:
                    print(f"   Rewrote ({tokens} tokens): {rewritten[:80]}")
                    
                    print(f"\n[3] Publishing to {target_channel}...")
                    message_id = await pub.publish_to_channel(rewritten, target_channel)
                    
                    if message_id:
                        print(f"   SUCCESS! Message ID: {message_id}")
                    else:
                        print(f"   FAILED - no message ID returned")
                else:
                    print(f"   FAILED - rewrite returned None")
            else:
                print("   No items fetched")
        else:
            print("   No active sources")

asyncio.run(test())
