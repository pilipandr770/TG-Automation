#!/usr/bin/env python
"""Debug publishing issues"""
import asyncio
import logging
import sys
from pathlib import Path

# Load env before importing app
from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models import AppConfig, PublishedPost, ContentSource
from app.services.telegram_client import TelegramClientManager
from app.services.openai_service import OpenAIService
from app.services.content_fetcher import ContentFetcher
from app.services.publisher_service import PublisherService

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = create_app()

async def debug():
    """Run debug diagnostics"""
    with app.app_context():
        # Check configuration
        target_channel = AppConfig.get('target_channel', 'NOT SET')
        print(f"[OK] Target channel: {target_channel}")
        
        # Check RSS sources
        sources = ContentSource.query.filter_by(active=True).all()
        print(f"[OK] Active sources: {len(sources)}")
        for source in sources:
            print(f"  - {source.name} (last_fetched: {source.last_fetched})")
        
        # Initialize services
        print("\n[INIT] Initializing services...")
        client_manager = TelegramClientManager()
        openai_service = OpenAIService()
        content_fetcher = ContentFetcher()
        publisher = PublisherService(client_manager, openai_service, content_fetcher)
        
        # Try to get Telegram client
        print("\n[CLIENT] Getting Telegram client...")
        try:
            client = await client_manager.get_client()
            if client:
                me = await client.get_me()
                print(f"[OK] Client connected: {me.first_name}")
            else:
                print("[ERROR] Client is None")
        except Exception as e:
            print(f"[ERROR] Client error: {e}")
        
        # Try to fetch content
        print("\n[FETCH] Fetching content...")
        try:
            # Get first source to test
            if sources:
                source = sources[0]
                print(f"Fetching from: {source.name}")
                
                # Reset last_fetched to force fetch
                source.last_fetched = None
                db.session.commit()
                
                items = await publisher.fetch_new_content()
                print(f"[OK] Got {len(items)} items")
                
                if items:
                    item = items[0]
                    print(f"\n[REWRITE] Item: {item['title'][:60]}")
                    
                    # Try rewriting
                    rewritten, tokens = await publisher.rewrite_content(item, 'en')
                    if rewritten:
                        print(f"[OK] Rewritten ({tokens} tokens): {rewritten[:100]}")
                        
                        # Try publishing
                        print(f"\n[PUBLISH] Publishing to {target_channel}")
                        message_id = await publisher.publish_to_channel(rewritten, target_channel)
                        if message_id:
                            print(f"[SUCCESS] Published! Message ID: {message_id}")
                        else:
                            print(f"[ERROR] Publishing failed (no message ID)")
                    else:
                        print(f"[ERROR] Rewrite failed")
                        # Check what OpenAIService returned
                        result = await publisher.openai_service.chat(
                            system_prompt="Test prompt",
                            user_message="Test message",
                            module="debug"
                        )
                        print(f"OpenAI result: {result}")
            else:
                print("[ERROR] No active sources")
        except Exception as e:
            logger.exception(f"Error: {e}")
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(debug())
