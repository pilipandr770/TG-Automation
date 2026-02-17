#!/usr/bin/env python3
"""Test publishing content to a channel."""
import asyncio
from app import create_app, db
from app.models import AppConfig, PublishedPost
from app.services.telegram_client import get_telegram_client_manager
from app.services.publisher_service import PublisherService
from app.services.content_fetcher import ContentFetcher
from app.services.openai_service import get_openai_service

async def trigger_publish():
    """Fetch, rewrite, and publish content."""
    app = create_app()
    
    with app.app_context():
        target_channel = AppConfig.get('target_channel')
        if not target_channel:
            print("❌ ERROR: target_channel not set")
            print("   Run: python set_target_channel.py cryptocurrency_media")
            return
        
        print("=" * 70)
        print("PUBLISHING CONTENT TO CHANNEL")
        print("=" * 70)
        
        # Get services
        client_mgr = get_telegram_client_manager()
        client_mgr.load_session_from_db()
        
        client = await client_mgr.get_client()
        if not client:
            print("❌ ERROR: Cannot connect to Telegram")
            return
        
        try:
            await client.connect()
            print(f"✓ Connected to Telegram")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return
        
        openai = get_openai_service()
        fetcher = ContentFetcher()
        publisher = PublisherService(client_mgr, openai, fetcher)
        
        # Run publish cycle
        print(f"\nTarget channel: {target_channel}")
        print("=" * 70)
        
        published_count = await publisher.run_publish_cycle(max_posts=2)
        
        print("=" * 70)
        print(f"✓ Published {published_count} posts")
        
        # Show recent published posts
        recent = PublishedPost.query.filter_by(
            status='published'
        ).order_by(PublishedPost.published_at.desc()).limit(3).all()
        
        if recent:
            print("\nRecent published posts:")
            for post in recent:
                print(f"  ✓ {post.source_title[:50]}")
                print(f"    Message ID: {post.telegram_message_id}")
        
        await client.disconnect()

if __name__ == '__main__':
    asyncio.run(trigger_publish())
