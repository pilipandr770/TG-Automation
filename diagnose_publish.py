#!/usr/bin/env python
"""
Diagnostic script to check why posts are failing to publish
"""
import sys
from app import create_app, db
from app.models import PublishedPost, AppConfig
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = create_app()

with app.app_context():
    print("=" * 70)
    print("📋 PUBLISHED POSTS DIAGNOSTIC")
    print("=" * 70)
    
    # Get all posts
    all_posts = PublishedPost.query.all()
    print(f"\nTotal posts in database: {len(all_posts)}")
    
    for idx, post in enumerate(all_posts, 1):
        print(f"\n--- Post #{idx} ---")
        print(f"Title: {post.source_title[:60] if post.source_title else 'N/A'}")
        print(f"Status: {post.status}")
        print(f"Created: {post.created_at}")
        print(f"Published: {post.published_at}")
        print(f"Telegram Message ID: {post.telegram_message_id}")
        print(f"Tokens Used: {post.tokens_used}")
        print(f"Channel: {post.telegram_channel}")
        
        # Show content preview
        if post.rewritten_content:
            preview = post.rewritten_content[:100].replace('\n', ' ')
            print(f"Content preview: {preview}...")
        elif post.original_content:
            preview = post.original_content[:100].replace('\n', ' ')
            print(f"Original preview: {preview}...")
    
    print("\n" + "=" * 70)
    print("⚙️ CONFIGURATION CHECK")
    print("=" * 70)
    
    target_channel = AppConfig.get('target_channel')
    print(f"\nTarget Channel (from DB): {target_channel}")
    
    # Check .env file
    env_target = os.getenv('TELEGRAM_PUBLISH_CHANNEL')
    print(f"Target Channel (from .env): {env_target}")
    
    openai_model = AppConfig.get('openai_model')
    print(f"OpenAI Model: {openai_model}")
    
    publish_interval = AppConfig.get('publisher_interval_minutes')
    print(f"Publish Interval: {publish_interval} minutes")
    
    print("\n" + "=" * 70)
    print("🔍 CHECKING OPENAI SERVICE")
    print("=" * 70)
    
    try:
        from app.services.openai_service import OpenAIService
        openai = OpenAIService()
        
        # Check if API key is set
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("\n❌ OPENAI_API_KEY not set in .env!")
        else:
            print(f"\n✅ OpenAI API Key is configured")
        
        # Try a simple test
        print("\nAttempting simple OpenAI test...")
        try:
            result = openai.rewrite_content("Test article", "Test writing a simple post")
            print(f"✅ OpenAI is working")
            print(f"   Response length: {len(result)} chars")
        except Exception as e:
            print(f"❌ OpenAI test failed: {e}")
            
    except Exception as e:
        print(f"❌ Could not import OpenAI service: {e}")
    
    print("\n" + "=" * 70)
    print("📱 CHECKING TELEGRAM CLIENT")
    print("=" * 70)
    
    try:
        from app.services.telegram_client import TelegramClient
        
        # Check if session exists
        session_file = 'telegram_session.session'
        if os.path.exists(session_file):
            print(f"\n✅ Telegram session file exists: {session_file}")
        else:
            print(f"\n❌ Telegram session file NOT found: {session_file}")
        
        # Check credentials
        api_id = os.getenv('TELEGRAM_API_ID')
        api_hash = os.getenv('TELEGRAM_API_HASH')
        phone = os.getenv('TELEGRAM_PHONE')
        
        if api_id and api_hash and phone:
            print(f"✅ Telegram credentials configured")
        else:
            print(f"❌ Missing Telegram credentials:")
            if not api_id:
                print(f"   - TELEGRAM_API_ID")
            if not api_hash:
                print(f"   - TELEGRAM_API_HASH")
            if not phone:
                print(f"   - TELEGRAM_PHONE")
                
    except Exception as e:
        print(f"❌ Could not check Telegram client: {e}")
    
    print("\n" + "=" * 70)
    print("🔗 CHECKING CONTENT SOURCES")
    print("=" * 70)
    
    from app.models import ContentSource
    sources = ContentSource.query.filter_by(active=True).all()
    print(f"\nActive RSS sources: {len(sources)}")
    
    for source in sources:
        print(f"  - {source.name} (Last fetched: {source.last_fetched})")
    
    print("\n" + "=" * 70)
