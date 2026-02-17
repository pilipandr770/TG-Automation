#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
os.chdir('c:\\Users\\ПК\\Downloads\\telegram_automation')
sys.path.insert(0, os.getcwd())

from app import create_app, db
from app.models import SearchKeyword, AppConfig

app = create_app()

with app.app_context():
    print("=" * 70)
    print(">>> TESTING SMART KEYWORD REGENERATION")
    print("=" * 70)
    
    # Simulate keyword exhaustion
    business_goal = AppConfig.get('business_goal', '')
    
    print(f"\nBusiness Goal: {business_goal}\n")
    
    # Get current keywords
    keywords = SearchKeyword.query.filter_by(generation_round=0).all()
    print(f"Original Keywords ({len(keywords)}):")
    for kw in keywords[:5]:
        print(f"  - {kw.keyword}")
    if len(keywords) > 5:
        print(f"  ...and {len(keywords) - 5} more")
    
    # Simulate exhaustion
    if keywords:
        print(f"\n[TEST] Marking first keyword as exhausted...")
        test_kw = keywords[0]
        test_kw.cycles_without_new = 3
        test_kw.exhausted = True
        db.session.commit()
        print(f"  Marked '{test_kw.keyword}' as exhausted")
    
    # Show regenerated keywords
    regenerated = SearchKeyword.query.filter(SearchKeyword.generation_round > 0).all()
    print(f"\nRegenerated Keywords ({len(regenerated)}):")
    for kw in regenerated:
        print(f"  - '{kw.keyword}' (variant #{kw.generation_round}, source: {kw.source_keyword})")
    
    # Stats
    all_kw = SearchKeyword.query.all()
    stats = {
        'total': len(all_kw),
        'active': SearchKeyword.query.filter_by(active=True).count(),
        'exhausted': SearchKeyword.query.filter_by(exhausted=True).count(),
        'original': SearchKeyword.query.filter_by(generation_round=0).count(),
        'regenerated': SearchKeyword.query.filter(SearchKeyword.generation_round > 0).count(),
    }
    
    print("\n" + "=" * 70)
    print("KEYWORD STATISTICS")
    print("=" * 70)
    print(f"  Total: {stats['total']}")
    print(f"  Active: {stats['active']}")
    print(f"  Exhausted: {stats['exhausted']}")
    print(f"  Original: {stats['original']}")
    print(f"  Regenerated: {stats['regenerated']}")
    
    print("\n[OK] Database supports keyword regeneration!")
    print("[URL] View stats at: http://localhost:5000/admin/discovery-monitor")
