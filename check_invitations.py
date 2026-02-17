#!/usr/bin/env python
"""Verify invitation system setup."""
from app import create_app, db
from app.models import InvitationTemplate, AppConfig, Contact

app = create_app()

with app.app_context():
    print("=" * 70)
    print("✅ INVITATION SYSTEM STATUS")
    print("=" * 70)
    
    # Check templates
    templates = InvitationTemplate.query.all()
    print(f"\n📧 TEMPLATES ({len(templates)} available):")
    for t in templates:
        status = "✅" if t.active else "❌"
        print(f"  {status} {t.name} (used {t.use_count} times)")
    
    # Check configuration
    print(f"\n⚙️  CONFIGURATION:")
    configs = [
        'invitation_batch_size',
        'invitation_cycle_interval_minutes',
        'invitation_min_delay_seconds',
        'invitation_max_delay_seconds',
    ]
    
    for config_key in configs:
        config = AppConfig.query.filter_by(key=config_key).first()
        if config:
            print(f"  ✅ {config_key} = {config.value}")
        else:
            print(f"  ❌ {config_key} - NOT CONFIGURED")
    
    # Check pending invitations
    print(f"\n👥 PENDING INVITATIONS:")
    pending = Contact.query.filter_by(invitation_sent=False).count()
    sent = Contact.query.filter_by(invitation_sent=True).count()
    total = Contact.query.count()
    
    print(f"  Total contacts: {total}")
    print(f"  Pending invitations: {pending}")
    print(f"  Already invited: {sent}")
    
    if pending == 0:
        print(f"  ℹ️  No pending contacts. System will wait for audience scanning.")
    else:
        print(f"  ✅ Ready to send {pending} invitations!")
    
    print("\n" + "=" * 70)
    print("🚀 SYSTEM READY - Run: python telethon_runner.py")
    print("=" * 70)
