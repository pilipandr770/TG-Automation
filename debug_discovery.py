#!/usr/bin/env python
"""Debug script to check discovery status."""
from app import create_app, db
from app.models import DiscoveredChannel, SearchKeyword

app = create_app()
with app.app_context():
    print('=== SEARCH KEYWORDS ===')
    keywords = SearchKeyword.query.filter_by(active=True).all()
    for kw in keywords:
        print(f'  {kw.keyword} (priority={kw.priority})')
    
    print()
    print('=== DISCOVERED CHANNELS ===')
    channels = DiscoveredChannel.query.all()
    print(f'Total: {len(channels)}')
    for status in ['found', 'joined', 'left', 'banned']:
        count = DiscoveredChannel.query.filter_by(status=status).count()
        print(f'  Status "{status}": {count}')
    
    print()
    print('=== RECENT CHANNELS ===')
    recent = DiscoveredChannel.query.order_by(DiscoveredChannel.created_at.desc()).limit(5).all()
    for ch in recent:
        print(f'  {ch.title} (@{ch.username}) - {ch.subscriber_count} subs - {ch.status} - {ch.created_at}')
