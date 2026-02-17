#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
os.chdir('c:\\Users\\ПК\\Downloads\\telegram_automation')
sys.path.insert(0, os.getcwd())

from app import create_app, db
from app.models import Contact, DiscoveredChannel

app = create_app()

with app.app_context():
    print("Adding test contacts for UI testing...\n")
    
    # Get first channel
    channel = DiscoveredChannel.query.first()
    if not channel:
        print("[ERROR] No joined channels found")
        sys.exit(1)
    
    test_contacts = [
        {
            'telegram_id': 12345001,
            'username': 'john_adult_fan',
            'first_name': 'John',
            'last_name': 'Doe',
            'category': 'target_audience',
            'status': 'identified',
            'confidence_score': 0.95,
            'source_channel_id': channel.id,
        },
        {
            'telegram_id': 12345002,
            'username': 'admin_channel',
            'first_name': 'Admin',
            'last_name': '',
            'category': 'admin',
            'status': 'identified',
            'confidence_score': 0.98,
            'source_channel_id': channel.id,
        },
        {
            'telegram_id': 12345003,
            'username': 'bot_promoter',
            'first_name': 'Bot',
            'last_name': 'Promoter',
            'category': 'bot',
            'status': 'identified',
            'confidence_score': 0.92,
            'source_channel_id': channel.id,
        },
        {
            'telegram_id': 12345004,
            'username': 'competitor_brand',
            'first_name': 'Competitor',
            'last_name': 'Account',
            'category': 'competitor',
            'status': 'identified',
            'confidence_score': 0.87,
            'source_channel_id': channel.id,
        },
        {
            'telegram_id': 12345005,
            'username': 'spam_messages',
            'first_name': 'Spammer',
            'last_name': '',
            'category': 'spam',
            'status': 'identified',
            'confidence_score': 0.45,
            'source_channel_id': channel.id,
        },
        {
            'telegram_id': 12345006,
            'username': 'sarah_interest_adult',
            'first_name': 'Sarah',
            'last_name': 'M',
            'category': 'target_audience',
            'status': 'identified',
            'confidence_score': 0.88,
            'source_channel_id': channel.id,
        },
    ]
    
    for contact_data in test_contacts:
        contact = Contact(**contact_data)
        db.session.add(contact)
    
    db.session.commit()
    
    print(f"[OK] Added {len(test_contacts)} test contacts\n")
    
    # Show stats
    stats = {
        'total': Contact.query.count(),
        'target_audience': Contact.query.filter_by(category='target_audience').count(),
        'admin': Contact.query.filter_by(category='admin').count(),
        'competitor': Contact.query.filter_by(category='competitor').count(),
        'bot': Contact.query.filter_by(category='bot').count(),
        'promoter': Contact.query.filter_by(category='promoter').count(),
        'spam': Contact.query.filter_by(category='spam').count(),
    }
    
    print("Statistics:")
    print(f"  Total: {stats['total']}")
    print(f"  Target Audience: {stats['target_audience']}")
    print(f"  Admins: {stats['admin']}")
    print(f"  Competitors: {stats['competitor']}")
    print(f"  Bots: {stats['bot']}")
    print(f"  Promoters: {stats['promoter']}")
    print(f"  Spam: {stats['spam']}")
    
    print("\n[OK] Test data ready! View at: http://localhost:5000/admin/contacts")
