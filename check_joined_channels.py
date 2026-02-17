#!/usr/bin/env python3
"""Examine joined channels in detail."""
from app import create_app, db
from app.models import DiscoveredChannel

app = create_app()

with app.app_context():
    joined = DiscoveredChannel.query.filter_by(is_joined=True).limit(15).all()
    
    print(f"=== JOINED CHANNELS DETAIL ({len(joined)} shown) ===\n")
    for i, ch in enumerate(joined, 1):
        print(f"{i}. {ch.title[:60]}")
        print(f"   ID: {ch.telegram_id}")
        print(f"   Username: {ch.username}")
        print(f"   Type: {ch.channel_type}")
        print(f"   Subscribers: {ch.subscriber_count}")
        print(f"   Last scanned: {ch.last_scanned_at}")
        print()
