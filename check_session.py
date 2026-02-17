#!/usr/bin/env python
"""Check Telethon session status"""
from app import create_app, db
from app.models import TelegramSession

app = create_app()

with app.app_context():
    session = TelegramSession.query.first()
    print(f'Session exists: {bool(session)}')
    if session:
        print(f'Session data length: {len(session.session_string)}')
        print(f'Created: {session.created_at}')
        print(f'Updated: {session.updated_at}')
        print(f'\nSession is likely EXPIRED - needs re-authentication')
