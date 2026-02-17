#!/usr/bin/env python3
"""Check discovery progress."""
from app import create_app, db
from app.models import DiscoveredChannel, SearchKeyword

app = create_app()

with app.app_context():
    channels = DiscoveredChannel.query.count()
    keywords = SearchKeyword.query.count()
    active_keywords = SearchKeyword.query.filter_by(active=True).count()
    
    print(f"=== DISCOVERY STATUS ===")
    print(f"Discovered channels: {channels}")
    print(f"Total keywords: {keywords}")
    print(f"Active keywords: {active_keywords}")
    
    # Show recent channels
    recent = DiscoveredChannel.query.order_by(DiscoveredChannel.created_at.desc()).limit(5).all()
    if recent:
        print(f"\n=== RECENT CHANNELS ===")
        for ch in recent:
            print(f"  - {ch.title} (ID: {ch.telegram_id})")
    else:
        print(f"\nNo channels discovered yet")
    
    # Show keyword status
    print(f"\n=== KEYWORD SAMPLE (first 5) ===")
    for kw in SearchKeyword.query.limit(5).all():
        print(f"  - '{kw.keyword}': active={kw.active}, cycles_without_new={kw.cycles_without_new}")
