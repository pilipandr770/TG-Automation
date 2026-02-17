#!/usr/bin/env python
"""Diagnostic script to test system components."""
import sys
import os

def test_imports():
    """Test basic imports."""
    print("=" * 60)
    print("TESTING IMPORTS")
    print("=" * 60)
    
    try:
        print("[1] Flask...", end=" ")
        from flask import Flask
        print("✅")
    except Exception as e:
        print(f"❌ {e}")
        return False
    
    try:
        print("[2] SQLAlchemy...", end=" ")
        from flask_sqlalchemy import SQLAlchemy
        print("✅")
    except Exception as e:
        print(f"❌ {e}")
        return False
    
    try:
        print("[3] Creating app...", end=" ")
        from app import create_app
        app = create_app()
        print("✅")
    except Exception as e:
        print(f"❌ {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        print("[4] App context...", end=" ")
        with app.app_context():
            from app.models import AppConfig
            count = AppConfig.query.count()
        print(f"✅ ({count} configs)")
    except Exception as e:
        print(f"❌ {e}")
        return False
    
    return True

def test_services():
    """Test service initialization."""
    print("\n" + "=" * 60)
    print("TESTING SERVICES")
    print("=" * 60)
    
    try:
        from app import create_app
        from app.services.openai_service import get_openai_service
        from app.services.telegram_client import get_telegram_client_manager
        
        app = create_app()
        with app.app_context():
            print("[1] OpenAI service...", end=" ")
            openai = get_openai_service()
            print("✅")
            
            print("[2] Telegram client...", end=" ")
            tg = get_telegram_client_manager()
            print("✅")
        
        return True
    except Exception as e:
        print(f"❌ {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database():
    """Test database connectivity."""
    print("\n" + "=" * 60)
    print("TESTING DATABASE")
    print("=" * 60)
    
    try:
        from app import create_app, db
        from app.models import (
            SearchKeyword, Contact, InvitationTemplate,
            ContentSource, Conversation, AppConfig
        )
        
        app = create_app()
        with app.app_context():
            kw = SearchKeyword.query.filter_by(active=True).count()
            ct = Contact.query.count()
            tpl = InvitationTemplate.query.filter_by(active=True).count()
            src = ContentSource.query.filter_by(active=True).count()
            conv = Conversation.query.count()
            
            print(f"✅ Keywords: {kw}")
            print(f"✅ Contacts: {ct}")
            print(f"✅ Templates: {tpl}")
            print(f"✅ Sources: {src}")
            print(f"✅ Conversations: {conv}")
        
        return True
    except Exception as e:
        print(f"❌ {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    all_ok = True
    all_ok = test_imports() and all_ok
    all_ok = test_services() and all_ok
    all_ok = test_database() and all_ok
    
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ ALL TESTS PASSED - SYSTEM READY")
    else:
        print("❌ TESTS FAILED - CHECK ERRORS ABOVE")
    print("=" * 60)
    
    sys.exit(0 if all_ok else 1)
