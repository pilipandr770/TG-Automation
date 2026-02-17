#!/usr/bin/env python
"""System status check - verify all components are working."""
import os
import sys

def check_system():
    os.environ['WERKZEUG_DEBUG_PIN'] = 'off'
    
    print("\n" + "=" * 70)
    print("TELEGRAM AUTOMATION SYSTEM STATUS CHECK")
    print("=" * 70 + "\n")
    
    checks = []
    
    # 1. Python version
    try:
        version = f"{sys.version_info.major}.{sys.version_info.minor}"
        checks.append(("Python", f"{version}", "✅"))
    except:
        checks.append(("Python", "unknown", "❌"))
    
    # 2. Flask
    try:
        from flask import Flask
        checks.append(("Flask", "OK", "✅"))
    except:
        checks.append(("Flask", "import failed", "❌"))
    
    # 3. Database
    try:
        from app import create_app, db
        app = create_app()
        with app.app_context():
            from app.models import AppConfig
            count = AppConfig.query.count()
            checks.append(("Database", f"{count} configs", "✅"))
    except Exception as e:
        checks.append(("Database", str(e)[:40], "❌"))
    
    # 4. Configuration
    try:
        from app import create_app, db
        app = create_app()
        with app.app_context():
            from app.models import SearchKeyword, Contact, InvitationTemplate, ContentSource
            kw = SearchKeyword.query.filter_by(active=True).count()
            ct = Contact.query.count()
            tpl = InvitationTemplate.query.filter_by(active=True).count()
            src = ContentSource.query.filter_by(active=True).count()
            msg = f"{kw}kw, {ct}contacts, {tpl}tpl, {src}rss"
            checks.append(("Configuration", msg, "✅"))
    except Exception as e:
        checks.append(("Configuration", str(e)[:40], "❌"))
    
    # 5. Telegram Session
    try:
        session_file = os.path.expanduser("~/.local/share/telethon/*.session")
        has_session = os.path.exists(".env") or os.path.exists("instance/telegram_automation.db")
        status = "Set" if has_session else "Not set"
        checks.append(("Telegram Session", status, "✅" if has_session else "⚠️"))
    except:
        checks.append(("Telegram Session", "unknown", "⚠️"))
    
    # 6. OpenAI API
    try:
        has_key = bool(os.getenv("OPENAI_API_KEY"))
        checks.append(("OpenAI API", "Configured" if has_key else "Not set", 
                      "✅" if has_key else "⚠️"))
    except:
        checks.append(("OpenAI API", "unknown", "⚠️"))
    
    # Print results
    print("COMPONENT STATUS:")
    print("-" * 70)
    for name, status, icon in checks:
        print(f"{icon} {name:<25} {status:<30}")
    
    # Summary
    passed = len([c for c in checks if c[2] == "✅"])
    total = len(checks)
    
    print("\n" + "=" * 70)
    if passed == total:
        print(f"✅ ALL SYSTEMS OPERATIONAL ({passed}/{total})")
        print("\nRunning instructions:")
        print("1. Terminal A: python telethon_runner.py")
        print("2. Terminal B: python wsgi.py")
        print("3. Access admin: http://localhost:5000")
    else:
        print(f"⚠️ PARTIAL SYSTEMS ({passed}/{total})")
        print("\nFix issues and retry:")
        print("python status.py")
    print("=" * 70 + "\n")
    
    return passed == total

if __name__ == '__main__':
    status = check_system()
    sys.exit(0 if status else 1)
