#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import sys
import os
os.chdir('c:\\Users\\ПК\\Downloads\\telegram_automation')
sys.path.insert(0, os.getcwd())

from app import create_app, db
from app.models import DiscoveredChannel, Contact, AudienceCriteria
from app.services.audience_service import AudienceService

async def run_scan():
    app = create_app()
    with app.app_context():
        print("=" * 70)
        print(">>> STARTING AUDIENCE SCAN")
        print("=" * 70)
        
        # Get joined channels
        joined_channels = DiscoveredChannel.query.filter_by(is_joined=True).all()
        print(f"\n[INFO] Found {len(joined_channels)} joined channels\n")
        
        # Show channels
        for i, ch in enumerate(joined_channels[:10], 1):
            print(f"  {i}. {ch.title} ({ch.subscriber_count} members)")
        if len(joined_channels) > 10:
            print(f"  ... and {len(joined_channels) - 10} more")
        
        # Check criteria
        criteria_list = AudienceCriteria.query.filter_by(active=True).all()
        if not criteria_list:
            print("\n[ERROR] No active audience criteria defined!")
            return
        
        print(f"\n[OK] Active criteria: {len(criteria_list)}")
        for crit in criteria_list:
            print(f"  - {crit.name}")
        
        # Clear old contacts for clean testing
        old_count = Contact.query.count()
        Contact.query.delete()
        db.session.commit()
        print(f"\n[OK] Cleared {old_count} old contacts from database\n")
        
        # Initialize audience service
        audience_service = AudienceService()
        
        print("[WAIT] Running scan...\n")
        
        try:
            # Run the scan
            result = await audience_service.run_audience_scan()
            
            print(f"\n[OK] Scan completed!")
            print(f"\nScan Results:")
            print(f"  Channels scanned: {result['channels_scanned']}")
            print(f"  Messages read: {result['messages_read']}")
            print(f"  Users analyzed: {result['users_analyzed']}")
            print(f"  Admins found: {result['admins_found']}")
            print(f"  Competitors found: {result['competitors_found']}")
            print(f"  Bots found: {result['bots_found']}")
            print(f"  Promoters found: {result['promoters_found']}")
            print(f"  Spam found: {result['spam_found']}")
            print(f"  Target audience found: {result['target_audience_found']}")
            print(f"  Contacts saved: {result['saved_contacts']}")
                    
        except Exception as e:
            print(f"[ERROR] During scan: {str(e)}")
            import traceback
            traceback.print_exc()
            return
        
        # Show final statistics
        print("\n" + "=" * 70)
        print(">>> FINAL STATISTICS")
        print("=" * 70)
        
        total_contacts = Contact.query.count()
        stats = {
            'total': total_contacts,
            'target_audience': Contact.query.filter_by(category='target_audience').count(),
            'admin': Contact.query.filter_by(category='admin').count(),
            'competitor': Contact.query.filter_by(category='competitor').count(),
            'bot': Contact.query.filter_by(category='bot').count(),
            'promoter': Contact.query.filter_by(category='promoter').count(),
            'spam': Contact.query.filter_by(category='spam').count(),
        }
        
        print(f"\nTotal contacts found: {stats['total']}")
        print(f"  [OK] Target Audience: {stats['target_audience']}")
        print(f"  [INFO] Admins: {stats['admin']}")
        print(f"  [WARN] Competitors: {stats['competitor']}")
        print(f"  [ERR] Bots: {stats['bot']}")
        print(f"  [INFO] Promoters: {stats['promoter']}")
        print(f"  [SPAM] Spam: {stats['spam']}")
        
        if stats['target_audience'] > 0:
            print(f"\n[SUCCESS] Found {stats['target_audience']} target audience contacts!")
            # Show top 5 by confidence
            top = Contact.query.filter_by(category='target_audience')\
                .order_by(Contact.confidence_score.desc())\
                .limit(5).all()
            
            if top:
                print("\nTop 5 by confidence:")
                for contact in top:
                    username = contact.username or contact.telegram_id
                    print(f"  - @{username}: {contact.confidence_score:.2f}")
        
        print("\n" + "=" * 70)
        print("[OK] View results at: http://localhost:5000/admin/contacts")
        print("=" * 70)

if __name__ == '__main__':
    try:
        asyncio.run(run_scan())
    except KeyboardInterrupt:
        print("\n\n[WARN] Scan interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
