#!/usr/bin/env python3
"""Find suitable channels for publishing and set target channel."""
from app import create_app, db
from app.models import DiscoveredChannel, AppConfig

app = create_app()

with app.app_context():
    print("=" * 70)
    print("FINDING SUITABLE CHANNELS FOR PUBLISHING")
    print("=" * 70)
    
    joined = DiscoveredChannel.query.filter_by(is_joined=True).order_by(
        DiscoveredChannel.title
    ).limit(20).all()
    
    print(f"\n✓ You have {len(joined)} joined channels\n")
    
    print("Channels available for publishing:\n")
    for i, ch in enumerate(joined, 1):
        print(f"{i:2}. {ch.title[:50]}")
        print(f"    Username: {ch.username or 'Private channel'}")
        print(f"    Type: {ch.channel_type}")
        print(f"    ID: {ch.telegram_id}")
        print()
    
    print("=" * 70)
    print("RECOMMENDATIONS FOR PUBLISHING:")
    print("=" * 70)
    print("""
Setting up publishing works better with channels where:
    ✓ You are the admin/owner
    ✓ The channel has a clear topic (tech, crypto, news, lifestyle, etc.)
    ✓ You want to post regularly

If you don't have a dedicated publishing channel yet, you should:
    1. Create a new private/public channel in Telegram
    2. Join it from this account
    3. Set it as the target channel

You can set target channel in two ways:

Option A: Set via admin panel
    - Go to /admin/settings
    - Add key 'target_channel' with value like: @your_channel_name

Option B: Set programmatically (will require channel selection)
    - Edit the next section and specify channel username or ID

Current target channel: {current}
    """.format(current=AppConfig.get('target_channel') or 'NOT SET'))
    
    print("\nTo use one of your joined channels for publishing, you can:")
    print("  python set_target_channel.py channel_username")
    print("\nFor example:")
    print(f"  python set_target_channel.py {joined[0].username or joined[0].telegram_id}")
