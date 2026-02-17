#!/usr/bin/env python3
"""Initialize publishing system with sample RSS feeds."""
from app import create_app, db
from app.models import ContentSource, AppConfig

app = create_app()

with app.app_context():
    print("Setting up publishing system...\n")
    
    # Clear old sources
    ContentSource.query.delete()
    db.session.commit()
    print("✓ Cleared old content sources")
    
    # Add quality RSS feeds
    feeds = [
        {
            'name': 'AI & Tech News (The Verge)',
            'url': 'https://www.theverge.com/rss/index.xml',
            'source_type': 'rss',
            'language': 'en',
            'fetch_interval_hours': 6
        },
        {
            'name': 'Crypto News (CoinTelegraph)',
            'url': 'https://cointelegraph.com/feed',
            'source_type': 'rss',
            'language': 'en',
            'fetch_interval_hours': 6
        },
        {
            'name': 'AI News (Hacker News)',
            'url': 'https://news.ycombinator.com/rss',
            'source_type': 'rss',
            'language': 'en',
            'fetch_interval_hours': 4
        },
        {
            'name': 'BBC News',
            'url': 'https://feeds.bbci.co.uk/news/rss.xml',
            'source_type': 'rss',
            'language': 'en',
            'fetch_interval_hours': 2
        },
        {
            'name': 'ArsTechnica',
            'url': 'https://feeds.arstechnica.com/arstechnica/index',
            'source_type': 'rss',
            'language': 'en',
            'fetch_interval_hours': 6
        },
    ]
    
    for feed_data in feeds:
        source = ContentSource(**feed_data)
        db.session.add(source)
        db.session.commit()
        print(f"✓ Added: {source.name}")
    
    print(f"\n✓ {len(feeds)} RSS feeds configured")
    
    # Set default configuration
    AppConfig.set('openai_prompt_publisher', 
        'Rewrite this article as an engaging Telegram post (max 4000 characters). '
        'Make it interesting, add relevant emojis, and include a call-to-action. '
        'Format: [emoji] Title\n\n[content with formatting]')
    
    print("✓ Set OpenAI prompt for publisher")
    
    # Note about target channel
    print("\n⚠️  NEXT STEPS:")
    print("1. Set target channel: Go to /admin/settings and add 'target_channel'")
    print("   (use format like: @your_channel or @username)")
    print("2. Check content sources at /admin/content-sources")
    print("3. Trigger publish manually via /admin (or API: POST /api/publish/trigger)")
    print("\nThe system will now:")
    print("  - Fetch content from RSS feeds every 2-6 hours")
    print("  - Rewrite it using OpenAI")
    print("  - Publish to your channel")
