#!/usr/bin/env python
"""Setup invitation templates and configuration."""
from app import create_app, db
from app.models import InvitationTemplate, AppConfig

app = create_app()

with app.app_context():
    print("=" * 70)
    print("📧 SETTING UP INVITATION TEMPLATES & CONFIGURATION")
    print("=" * 70)
    
    # Step 1: Create invitation templates
    print("\n[STEP 1] Creating invitation templates...")
    
    templates = [
        {
            'name': 'Welcome to Our Community',
            'body': """🎉 **Welcome, {first_name}!**

We noticed your interest in crypto and technology. We've created a private community exclusively for people like you.

Join us at **@online_crypto_bonuses** where we share:
✨ Daily crypto market insights
💰 Profitable trading opportunities
🔐 Security tips for crypto
🎁 Exclusive deals and offers
🌐 Networking with crypto enthusiasts

**Join now and become part of our thriving community!**

Looking forward to seeing you there! 🚀""",
            'language': 'en'
        },
        {
            'name': 'Exclusive Crypto Opportunity',
            'body': """Hey {first_name}! 👋

Exciting news! We've curated **premium crypto content** just for members like you.

In our group, you'll get:
💎 Early access to profitable trades
📊 Real-time market analysis
🎯 Expert recommendations
💰 Limited-time investment opportunities
🔔 Instant alerts on price movements

**@online_crypto_bonuses** - Join thousands of smart investors! 🚀

See you there!""",
            'language': 'en'
        },
        {
            'name': 'Tech & Crypto News Hub',
            'body': """Hi {first_name}! 👨‍💻

Are you into tech and crypto? Perfect!

Our community **@online_crypto_bonuses** is your go-to place for:
🔬 Latest AI & Tech breakthroughs
💻 Blockchain innovations
🎮 Web3 & Metaverse updates
💡 Smart investment strategies
🤝 Connect with industry experts

**Join now and stay ahead of the curve!** 🌟

See you in the group!""",
            'language': 'en'
        },
        {
            'name': 'Community VIP Invitation',
            'body': """Dear {first_name}, 🌟

You've been selected for **VIP access** to our exclusive community!

This is a **limited opportunity** for passionate crypto enthusiasts like you.

Inside **@online_crypto_bonuses** you'll discover:
🎁 VIP-only tips and strategies
📈 Market predictions & analysis
💼 Networking opportunities
🏆 Success stories from members
🚀 Fast-growing wealth strategies

**Claim your VIP spot now!**

Let's grow together! 💪""",
            'language': 'en'
        },
        {
            'name': 'Quick Join Invitation',
            'body': """Hi {first_name}! 👋

Just a quick message - we think you'd love our community!

Join **@online_crypto_bonuses** for:
✅ Daily market updates
✅ Trading tips that work
✅ Community support
✅ Exclusive opportunities
✅ Fun discussions

**Click here and come join us!** 🎯

See you there!""",
            'language': 'en'
        },
    ]
    
    for template_data in templates:
        existing = InvitationTemplate.query.filter_by(name=template_data['name']).first()
        if existing:
            print(f"  ⚠️  Template '{template_data['name']}' already exists")
        else:
            template = InvitationTemplate(
                name=template_data['name'],
                body=template_data['body'],
                language=template_data['language'],
                active=True,
                use_count=0
            )
            db.session.add(template)
            print(f"  ✅ Created: {template_data['name']}")
    
    db.session.commit()
    print(f"\n✅ {len(templates)} templates configured")
    
    # Step 2: Setup configuration
    print("\n[STEP 2] Configuring invitation system...")
    
    configs = {
        'invitation_batch_size': ('5', 'How many invitations per cycle'),
        'invitation_cycle_interval_minutes': ('10', 'Minutes between invitation cycles'),
        'invitation_min_delay_seconds': ('120', 'Min delay between invitations (2 min)'),
        'invitation_max_delay_seconds': ('180', 'Max delay between invitations (3 min)'),
    }
    
    for key, (value, description) in configs.items():
        existing = AppConfig.query.filter_by(key=key).first()
        if existing:
            print(f"  ⚠️  Config '{key}' already exists: {existing.value}")
        else:
            config = AppConfig(key=key, value=value, description=description)
            db.session.add(config)
            print(f"  ✅ Set {key} = {value}")
    
    db.session.commit()
    
    print("\n" + "=" * 70)
    print("✅ INVITATION SYSTEM READY!")
    print("=" * 70)
    print("""
Configuration:
  • Batch size: 5 people per cycle
  • Cycle interval: 10 minutes
  • Delay between invites: 2-3 minutes
  • Templates: 5 different messages (random selection)

Features:
  ✅ Sends invitations only once per person
  ✅ Random template selection
  ✅ Random delays to avoid spam detection
  ✅ Skips already-invited users
  ✅ Logs all invitation attempts

Next step:
  Run: python telethon_runner.py
  System will start sending invitations automatically!
    """)
    print("=" * 70)
