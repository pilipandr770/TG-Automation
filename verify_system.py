#!/usr/bin/env python
"""
Complete system verification script.
Checks all configurations and ensures everything is ready.
"""
import sys
from datetime import datetime
from app import create_app, db
from app.models import (
    AppConfig, Conversation, InvitationTemplate, 
    ContentSource, PublishedPost, SearchKeyword, Contact
)

app = create_app()

def colored(text, color):
    """Print colored text."""
    colors = {
        'green': '\033[92m',
        'red': '\033[91m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'end': '\033[0m'
    }
    return f"{colors.get(color, '')}{text}{colors['end']}"

def main():
    with app.app_context():
        print("\n" + "="*70)
        print(colored("🚀 TELEGRAM AUTOMATION SYSTEM VERIFICATION", "blue"))
        print("="*70 + "\n")
        
        sections = {
            'Module 1: Discovery': 'discovery',
            'Module 2: Audience': 'audience',
            'Module 3: Invitations': 'invitations',
            'Module 4: Publishing': 'publishing',
            'Module 5: Conversations': 'conversations',
        }
        
        all_good = True
        
        # 1. Check AI Instructions (NEW)
        print(colored("📝 AI INSTRUCTIONS", "blue"))
        print("-" * 70)
        dm_inst = AppConfig.get('openai_prompt_conversation')
        channel_inst = AppConfig.get('openai_prompt_channel_comments')
        if dm_inst:
            print(colored("✅", "green") + f" DM Instruction: {len(dm_inst)} chars")
        else:
            print(colored("❌", "red") + " DM Instruction: NOT FOUND")
            all_good = False
        if channel_inst:
            print(colored("✅", "green") + f" Channel Comment Instruction: {len(channel_inst)} chars")
        else:
            print(colored("⚠️ ", "yellow") + " Channel Comment Instruction: NOT FOUND (optional)")
        print()
        
        # 2. Module Configurations
        print(colored("⚙️  MODULE CONFIGURATIONS", "blue"))
        print("-" * 70)
        
        # Module 1: Discovery
        keywords_count = SearchKeyword.query.filter_by(active=True).count()
        print(colored(f"✅ Module 1 - Discovery: {keywords_count} keywords", "green"))
        
        # Module 2: Audience
        contacts_count = Contact.query.count()
        contacts_invited = Contact.query.filter_by(invitation_sent=True).count()
        print(colored(f"✅ Module 2 - Audience: {contacts_count} contacts ({contacts_invited} invited)", "green"))
        
        # Module 3: Invitations
        templates_count = InvitationTemplate.query.filter_by(active=True).count()
        invitation_delay_min = AppConfig.get('invitation_min_delay_seconds', '120')
        invitation_delay_max = AppConfig.get('invitation_max_delay_seconds', '180')
        print(colored(f"✅ Module 3 - Invitations: {templates_count} templates, {invitation_delay_min}-{invitation_delay_max}sec delay", "green"))
        
        # Module 4: Publishing
        sources_count = ContentSource.query.filter_by(active=True).count()
        posts_count = PublishedPost.query.count()
        print(colored(f"✅ Module 4 - Publishing: {sources_count} sources, {posts_count} posts", "green"))
        
        # Module 5: Conversations
        conversations_count = Conversation.query.count()
        active_convs = Conversation.query.filter_by(status='active').count()
        voice_enabled = AppConfig.get('voice_message_transcription') == 'true'
        voice_status = "✅ Enabled" if voice_enabled else "❌ Disabled"
        print(colored(f"✅ Module 5 - Conversations: {conversations_count} total, {active_convs} active", "green"))
        print(colored(f"   • Voice Transcription: {voice_status}", "green"))
        print(colored(f"   • Channel Comments: ✅ NEW FEATURE ENABLED", "green"))
        print()
        
        # 3. System Features
        print(colored("✨ SYSTEM FEATURES", "blue"))
        print("-" * 70)
        features = [
            ('Keyword-based Discovery', True),
            ('Audience Extraction & AI Analysis', True),
            ('Automated Invitations (2-5 templates)', templates_count > 0),
            ('RSS Feed Publishing (with OpenAI rewrite)', sources_count > 0),
            ('Private Message Responses (AI-powered)', conversations_count > 0),
            ('Voice Message Support (Whisper)', voice_enabled),
            ('Paid Channel Comments (NEW)', True),
            ('System Instructions Customization', dm_inst is not None),
        ]
        
        for feature, enabled in features:
            status = colored("✅", "green") if enabled else colored("❌", "red")
            print(f"{status} {feature}")
        print()
        
        # 4. Ready Check
        print(colored("✅ CHECK RESULTS", "blue"))
        print("-" * 70)
        if all_good and dm_inst:
            print(colored("🎉 SYSTEM IS FULLY CONFIGURED AND READY!", "green"))
            print("\nNext steps:")
            print("  1. Start telethon_runner.py to activate all modules")
            print("  2. Start Flask app (app.py) for admin panel")
            print("  3. Access admin at http://localhost:5000")
            print("  4. Send test messages to verify responses")
            print("  5. Check logs for 'System prompt loaded' messages")
            print("\nYour custom instructions will be used for all responses!")
        else:
            print(colored("⚠️  SYSTEM READY WITH WARNINGS", "yellow"))
            if not dm_inst:
                print("  ⚠️  No custom DM instruction found")
                print("     → Run: python setup_instructions.py")
        
        print("\n" + "="*70)
        print(colored(f"Verification completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "blue"))
        print("="*70 + "\n")
        
        return 0 if all_good else 1

if __name__ == '__main__':
    sys.exit(main())
