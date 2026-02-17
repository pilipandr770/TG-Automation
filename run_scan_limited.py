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

async def run_limited_scan():
    app = create_app()
    with app.app_context():
        print("=" * 70)
        print(">>> AUDIENCE SCAN - CHANNELS WITH COMMENTS")
        print("=" * 70)
        
        # Get channels with comments enabled (more likely to have real users)
        all_joined = DiscoveredChannel.query.filter_by(is_joined=True).all()
        with_comments = DiscoveredChannel.query.filter_by(is_joined=True, has_comments=True).all()
        
        print(f"\n[INFO] Total joined channels: {len(all_joined)}")
        print(f"[INFO] Channels with comments: {len(with_comments)}\n")
        
        # Show channels with comments
        for i, ch in enumerate(with_comments[:10], 1):
            print(f"  {i}. {ch.title} ({ch.subscriber_count} members)")
        if len(with_comments) > 10:
            print(f"  ... and {len(with_comments) - 10} more")
        
        # Check criteria
        criteria_list = AudienceCriteria.query.filter_by(active=True).all()
        if not criteria_list:
            print("\n[ERROR] No active audience criteria defined!")
            return
        
        print(f"\n[OK] Active criteria: {len(criteria_list)}")
        for crit in criteria_list:
            print(f"  - {crit.name}")
        
        # Clear old contacts
        old_count = Contact.query.count()
        Contact.query.delete()
        db.session.commit()
        print(f"\n[OK] Cleared {old_count} old contacts\n")
        
        # Initialize audience service
        audience_service = AudienceService()
        
        print("[WAIT] Scanning channels with comments...\n")
        
        try:
            # Run the full scan (it will handle all joined channels internally)
            result = await audience_service.run_audience_scan()
            
            print(f"\n[OK] Scan completed!")
            print(f"\nResults:")
            print(f"  Channels scanned: {result['channels_scanned']}")
            print(f"  Messages read: {result['messages_read']}")
            print(f"  Users analyzed: {result['users_analyzed']}")
            print(f"  Target audience found: {result['target_audience_found']}")
            print(f"  Contacts saved: {result['saved_contacts']}")
            
            if result['users_analyzed'] > 0:
                print(f"\n[INFO] Breakdown of analyzed users:")
                print(f"    Admins: {result['admins_found']}")
                print(f"    Competitors: {result['competitors_found']}")
                print(f"    Bots: {result['bots_found']}")
                print(f"    Promoters: {result['promoters_found']}")
                print(f"    Spam: {result['spam_found']}")
                    
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
        
        print(f"\nTotal contacts: {stats['total']}")
        if stats['total'] > 0:
            print(f"  [OK] Target Audience: {stats['target_audience']}")
            print(f"  [INFO] Admins: {stats['admin']}")
            print(f"  [WARN] Competitors: {stats['competitor']}")
            print(f"  [ERR] Bots: {stats['bot']}")
            print(f"  [INFO] Promoters: {stats['promoter']}")
            print(f"  [SPAM] Spam: {stats['spam']}")
            
            if stats['target_audience'] > 0:
                print(f"\n[SUCCESS] Found {stats['target_audience']} target audience contacts!")
                top = Contact.query.filter_by(category='target_audience')\
                    .order_by(Contact.confidence_score.desc())\
                    .limit(5).all()
                
                if top:
                    print("\nTop 5 by confidence:")
                    for contact in top:
                        username = contact.username or contact.telegram_id
                        print(f"  - @{username}: {contact.confidence_score:.2f}")
        else:
            print("\n[WARN] No contacts found in this scan")
            print("[INFO] This might be due to:")
            print("  - Channels without message access")
            print("  - No active users in sampled messages")
            print("  - Rate limiting from Telegram API")
        
        print("\n" + "=" * 70)
        print("[OK] View all results at: http://localhost:5000/admin/contacts")
        print("=" * 70)

if __name__ == '__main__':
    try:
        asyncio.run(run_limited_scan())
    except KeyboardInterrupt:
        print("\n\n[WARN] Scan interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
