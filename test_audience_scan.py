#!/usr/bin/env python
"""Test audience scanning with detailed debug output."""
import asyncio
import sys
from app import create_app, db
from app.models import DiscoveredChannel, AudienceCriteria, Contact
from app.services.audience_service import AudienceService

async def test_scan():
    app = create_app()
    with app.app_context():
        print('=== STARTING TEST AUDIENCE SCAN ===\n')
        
        # Check what we have
        joined_channels = DiscoveredChannel.query.filter_by(is_joined=True).all()
        print(f'[INFO] Joined channels: {len(joined_channels)}')
        for ch in joined_channels[:3]:
            print(f'  - {ch.title} (ID: {ch.telegram_id})')
        
        criteria_list = AudienceCriteria.query.filter_by(active=True).all()
        print(f'\n[INFO] Active criteria: {len(criteria_list)}')
        for c in criteria_list:
            print(f'  - {c.name} (min_confidence: {c.min_confidence})')
        
        if not joined_channels:
            print('\n[ERROR] No joined channels found!')
            return
        
        if not criteria_list:
            print('\n[ERROR] No active criteria found!')
            return
        
        # Run scan
        print('\n[INFO] Starting audience scan...\n')
        service = AudienceService()
        result = await service.run_audience_scan()
        
        # Show results
        print('\n=== SCAN RESULTS ===')
        print(f'Channels scanned: {result["channels_scanned"]}')
        print(f'Messages read: {result["messages_read"]}')
        print(f'Users analyzed: {result["users_analyzed"]}')
        print(f'Admins found: {result["admins_found"]}')
        print(f'Bots found: {result["bots_found"]}')
        print(f'Spam found: {result["spam_found"]}')
        print(f'Competitors found: {result["competitors_found"]}')
        print(f'Target audience found: {result["target_audience_found"]}')
        print(f'Saved contacts: {result["saved_contacts"]}')
        
        # Check database
        print('\n[INFO] Contacts in database:')
        total = Contact.query.count()
        print(f'  Total: {total}')
        target = Contact.query.filter_by(category='target_audience').count()
        print(f'  Target audience: {target}')
        
        if total > 0:
            print('\n[SUCCESS] Contacts saved!')
            samples = Contact.query.limit(3).all()
            for contact in samples:
                user = contact.username or contact.first_name or 'Unknown'
                print(f'  @{user}: confidence={contact.confidence_score:.2f}, category={contact.category}')
        else:
            print('\n[WARN] No contacts saved. This is expected if:')
            print('  1. No messages were read from channels')
            print('  2. No users matched the criteria')
            print('  3. Confidence scores are below threshold')

asyncio.run(test_scan())
