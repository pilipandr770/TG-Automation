#!/usr/bin/env python
from app import create_app, db
from app.models import AudienceCriteria, Contact

app = create_app()
with app.app_context():
    print('=== AUDIENCE CRITERIA ===')
    criteria_list = AudienceCriteria.query.all()
    if not criteria_list:
        print('No criteria found! First, create audience criteria.')
    else:
        for c in criteria_list:
            print(f'Name: {c.name}')
            print(f'  Min Confidence: {c.min_confidence}')
            kw = c.keywords[:50] if c.keywords else 'None'
            print(f'  Keywords: {kw}')
            print(f'  Active: {c.active}')
            print()
    
    print('=== CONTACTS IN DATABASE ===')
    total = Contact.query.count()
    print(f'Total contacts: {total}')
    target = Contact.query.filter_by(category='target_audience').count()
    print(f'Target audience: {target}')
    admin = Contact.query.filter_by(category='admin').count()
    print(f'Admin: {admin}')
    bot = Contact.query.filter_by(category='bot').count()
    print(f'Bot: {bot}')
    spam = Contact.query.filter_by(category='spam').count()
    print(f'Spam: {spam}')
    competitor = Contact.query.filter_by(category='competitor').count()
    print(f'Competitor: {competitor}')
    
    print('\n=== SAMPLE CONTACTS ===')
    contacts = Contact.query.limit(10).all()
    if not contacts:
        print('No contacts in database yet.')
    else:
        for contact in contacts:
            user = contact.username or contact.first_name or 'Unknown'
            print(f'@{user}: confidence={contact.confidence_score:.2f}, category={contact.category}')
