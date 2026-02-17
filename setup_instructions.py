#!/usr/bin/env python
"""Setup conversation system with instructions for both DM and channel comments."""
import sys
from app import create_app, db
from app.models import AppConfig

app = create_app()

def setup_conversation_instructions():
    """Configure conversation AI settings."""
    
    with app.app_context():
        # System instruction for private messages
        dm_instruction = """You are a helpful and friendly assistant for our Telegram community.
        
IMPORTANT RULES:
1. Be concise and friendly
2. Respond in the same language the user is using
3. Keep responses short (2-3 sentences max)
4. Be informative but not preachy
5. Ask clarifying questions if needed
6. Never share sensitive information
7. Provide value in every response
8. Stay on topic

When responding to users, remember:
- They may be busy, so be brief
- Use emojis occasionally (but not excessively)
- Be personable and warm
- Provide specific, actionable advice
- Ask follow-up questions to understand better"""

        # System instruction for channel comments (paid)
        channel_instruction = """You are a professional community moderator responding to paid comments.

IMPORTANT RULES:
1. Be professional but warm
2. Acknowledge the value they paid (Stars)
3. Provide a high-quality response
4. Keep it concise (2-3 sentences)
5. Thank them for participating
6. Address their question/comment directly
7. Provide value immediately
8. Encourage further engagement

Remember:
- This is a premium interaction (they paid)
- Give them special attention
- Be thoughtful and helpful
- Make them feel appreciated"""

        # Save both instruction types
        configs = [
            ('openai_prompt_conversation', dm_instruction, 'System instruction for private messages and DM conversations'),
            ('openai_prompt_channel_comments', channel_instruction, 'System instruction for paid channel comments'),
            ('voice_message_transcription', 'true', 'Enable voice message transcription via Whisper'),
            ('conversation_history_limit', '20', 'Number of messages to keep in conversation context'),
            ('auto_reply_enabled', 'true', 'Enable automatic responses to messages'),
        ]
        
        for key, value, description in configs:
            try:
                AppConfig.set(key, value, description)
                db.session.commit()
                print(f"✅ Saved: {key}")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Failed to save {key}: {e}")
                return False
        
        print("\n" + "=" * 60)
        print("✅ CONVERSATION SYSTEM SETUP COMPLETE")
        print("=" * 60)
        print("\nConfiguration saved:")
        print("  ✅ DM Instruction: For private messages")
        print("  ✅ Channel Comment Instruction: For paid channel comments")
        print("  ✅ Voice Transcription: Enabled")
        print("  ✅ History Limit: 20 messages")
        print("  ✅ Auto-Reply: Enabled")
        print("\nYou can now:")
        print("  1. Start telethon_runner.py to receive messages")
        print("  2. Send/receive messages - AI will respond automatically")
        print("  3. Enable paid comments in your channel")
        print("  4. Subscribers can comment and AI will reply")
        print("=" * 60)
        
        return True

if __name__ == '__main__':
    success = setup_conversation_instructions()
    sys.exit(0 if success else 1)
