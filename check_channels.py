#!/usr/bin/env python3
"""Check channel joining and audience scanning progress."""
from app import create_app, db
from app.models import DiscoveredChannel, Contact

app = create_app()

with app.app_context():
    total_channels = DiscoveredChannel.query.count()
    joined_channels = DiscoveredChannel.query.filter_by(is_joined=True).count()
    scanned_channels = DiscoveredChannel.query.filter(DiscoveredChannel.last_scanned_at.isnot(None)).count()
    
    print(f"=== CHANNEL STATUS ===")
    print(f"Total discovered: {total_channels}")
    print(f"Joined: {joined_channels}")
    print(f"Scanned for audience: {scanned_channels}")
    
    # Show some joined channels
    joined = DiscoveredChannel.query.filter_by(is_joined=True).limit(10).all()
    if joined:
        print(f"\n=== JOINED CHANNELS (first 10) ===")
        for ch in joined:
            contacts_count = Contact.query.filter_by(source_channel_id=ch.id).count()
            print(f"  - {ch.title} ({contacts_count} contacts found)")
    else:
        print(f"\nNo channels joined yet")
    
    # Show contact count
    total_contacts = Contact.query.count()
    target_contacts = Contact.query.filter_by(category='target_audience').count()
    
    print(f"\n=== CONTACT STATUS ===")
    print(f"Total contacts: {total_contacts}")
    print(f"Target audience: {target_contacts}")
