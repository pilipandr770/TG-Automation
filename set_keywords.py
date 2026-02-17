#!/usr/bin/env python
"""Update keywords for testing."""
from app import create_app, db
from app.models import SearchKeyword

app = create_app()
with app.app_context():
    # Clear old and add test keywords
    SearchKeyword.query.delete()
    db.session.commit()
    
    # Add keywords that we know exist in the account
    keywords = ['love', 'matskevich', 'sura', 'pussy']
    for i, kw in enumerate(keywords):
        sk = SearchKeyword(keyword=kw, priority=100-i)
        db.session.add(sk)
    db.session.commit()
    print(f'Added {len(keywords)} test keywords')
