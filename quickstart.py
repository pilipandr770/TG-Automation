#!/usr/bin/env python
"""Quick start guide for Telegram Automation System."""
import os
import sys
import subprocess
import time

print("\n" + "=" * 70)
print("TELEGRAM AUTOMATION SYSTEM - QUICK START GUIDE")
print("=" * 70 + "\n")

print("📋 PRE-FLIGHT CHECKLIST:")
print("-" * 70)

checks = {
    "Python 3.8+": sys.version_info >= (3, 8),
    "Database exists": os.path.exists("instance/telegram_automation.db"),
    ".env file": os.path.exists(".env"),
    "requirements.txt": os.path.exists("requirements.txt"),
}

all_ok = True
for check, status in checks.items():
    icon = "✅" if status else "❌"
    print(f"{icon} {check}")
    if not status and check != ".env file":
        all_ok = False

print("\n📝 SETUP INSTRUCTIONS:")
print("-" * 70)
print("""
1. Install dependencies:
   pip install -r requirements.txt

2. Create .env file (if not exists):
   TELEGRAM_API_ID=your_api_id
   TELEGRAM_API_HASH=your_api_hash
   TELEGRAM_PHONE=+1234567890
   TELEGRAM_TARGET_CHANNEL=@your_channel
   OPENAI_API_KEY=sk-...

3. Verify configuration:
   python status.py

4. Run the system:
   Terminal A: python telethon_runner.py
   Terminal B: python wsgi.py
   
5. Access admin panel:
   http://localhost:5000
   (default: admin / admin)
""")

print("\n" + "=" * 70)
if all_ok:
    print("✅ SYSTEM READY - Run the commands above")
else:
    print("⚠️  ISSUES DETECTED - Fix them before running")

print("=" * 70)
print("\n📚 For more info, see README.md\n")
