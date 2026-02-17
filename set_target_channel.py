#!/usr/bin/env python3
"""Script to set target channel for publishing."""
import sys
from app import create_app, db
from app.models import DiscoveredChannel, AppConfig

app = create_app()

with app.app_context():
    if len(sys.argv) < 2:
        print("Usage: python set_target_channel.py <channel_username_or_id>")
        print("\nExample: python set_target_channel.py cryptocurrency_media")
        print("Example: python set_target_channel.py 1488075213")
        sys.exit(1)
    
    channel_ref = sys.argv[1]
    
    # Try to find channel by username or ID
    if channel_ref.isdigit():
        channel = DiscoveredChannel.query.filter_by(telegram_id=int(channel_ref)).first()
    else:
        channel = DiscoveredChannel.query.filter_by(username=channel_ref).first()
    
    if not channel:
        print(f"❌ Channel not found: {channel_ref}")
        print("\nAvailable channels:")
        channels = DiscoveredChannel.query.filter_by(is_joined=True).all()
        for ch in channels[:10]:
            print(f"  - {ch.username or ch.telegram_id}: {ch.title}")
        sys.exit(1)
    
    # Set target channel - use username if available, else use ID
    target_channel = f"@{channel.username}" if channel.username else str(channel.telegram_id)
    
    AppConfig.set('target_channel', target_channel, description='Target channel for content publishing')
    
    print("✅ Target channel configured!")
    print(f"   Channel: {channel.title}")
    print(f"   Username: {channel.username or 'N/A'}")
    print(f"   Type: {channel.channel_type}")
    print(f"   Target value set to: {target_channel}")
    print("\n✓ Ready to publish!")
    print("  Trigger with: python trigger_publish.py")
