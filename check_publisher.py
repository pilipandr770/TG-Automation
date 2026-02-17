#!/usr/bin/env python3
"""Diagnostic script for content publishing system."""
from app import create_app, db
from app.models import ContentSource, PublishedPost, AppConfig
from app.services.content_fetcher import ContentFetcher
from app.services.openai_service import get_openai_service
import json

app = create_app()

with app.app_context():
    print("=" * 70)
    print("CONTENT PUBLISHING SYSTEM DIAGNOSTIC")
    print("=" * 70)
    
    # 1. Check configured content sources
    sources = ContentSource.query.all()
    print(f"\n=== CONTENT SOURCES ({len(sources)} configured) ===")
    if sources:
        for src in sources:
            print(f"  {src.id}. {src.name}")
            print(f"     Type: {src.source_type} | URL: {src.url}")
            print(f"     Language: {src.language} | Active: {src.active}")
            print(f"     Fetch interval: {src.fetch_interval_hours}h | Last fetched: {src.last_fetched}")
    else:
        print("  ⚠️  NO CONTENT SOURCES CONFIGURED")
        print("  Need to add RSS feeds, Reddit URLs, or webpages")
    
    # 2. Check published posts
    posts = PublishedPost.query.all()
    published = PublishedPost.query.filter_by(status='published').count()
    print(f"\n=== PUBLISHED POSTS ({published}/{len(posts)} published) ===")
    if posts:
        recent = PublishedPost.query.order_by(PublishedPost.created_at.desc()).limit(5).all()
        for post in recent:
            status_emoji = "✅" if post.status == 'published' else "❌" if post.status == 'failed' else "⏳"
            print(f"  {status_emoji} {post.source_title[:50]}")
            print(f"     Status: {post.status} | Published: {post.published_at}")
    else:
        print("  No posts published yet")
    
    # 3. Check OpenAI settings
    openai = get_openai_service()
    daily_budget = openai._get_daily_budget()
    model = openai._get_model()
    budget_ok = openai._check_budget()
    
    print(f"\n=== OPENAI CONFIGURATION ===")
    print(f"  Model: {model}")
    print(f"  Daily budget: ${daily_budget}")
    print(f"  Budget OK: {budget_ok}")
    
    # 4. Check publisher config
    target_channel = AppConfig.get('target_channel')
    default_language = AppConfig.get('default_language', 'en')
    custom_prompt = AppConfig.get('openai_prompt_publisher')
    
    print(f"\n=== PUBLISHER CONFIGURATION ===")
    print(f"  Target channel: {target_channel}")
    print(f"  Default language: {default_language}")
    print(f"  Custom prompt set: {bool(custom_prompt)}")
    
    # 5. Test RSS fetching with a sample URL
    print(f"\n=== TESTING CONTENT FETCHER ===")
    fetcher = ContentFetcher()
    
    test_rss_urls = [
        "https://news.ycombinator.com/rss",
        "https://feeds.arstechnica.com/arstechnica/index",
        "https://www.theverge.com/rss/index.xml",
    ]
    
    for test_url in test_rss_urls:
        try:
            print(f"\n  Testing RSS: {test_url[:50]}...")
            items = fetcher.fetch_rss(test_url)
            if items:
                print(f"    ✅ Fetched {len(items)} items")
                sample = items[0]
                print(f"    Sample title: {sample['title'][:60]}")
                break
            else:
                print(f"    ❌ No items returned")
        except Exception as e:
            print(f"    ❌ Error: {str(e)[:60]}")
    
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS:")
    print("=" * 70)
    if not sources:
        print("1. ADD RSS FEEDS:")
        print("   - Go to /admin/content-sources")
        print("   - Add RSS feeds like:")
        print("     * https://news.ycombinator.com/rss (Tech news)")
        print("     * https://feeds.arstechnica.com/arstechnica/index (Tech)")
        print("     * https://feeds.bbci.co.uk/news/rss.xml (News)")
        print("     * https://cointelegraph.com/feed (Crypto)")
    
    if not budget_ok:
        print("2. CHECK OPENAI BUDGET:")
        print("   - Daily budget exceeded or API key missing")
        print("   - Update budget in /admin/settings")
    
    if not target_channel:
        print("3. SET TARGET CHANNEL:")
        print("   - Go to /admin/settings")
        print("   - Set 'target_channel' to your Telegram channel (@your_channel)")
    
    print("\n✅ Configuration check complete")
