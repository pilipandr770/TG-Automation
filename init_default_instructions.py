"""
Initialize default chatbot instructions in the database.
Run this once after deploying the API.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import AppConfig

def init_instructions():
    """Initialize default instructions for chatbot."""
    app = create_app()
    
    with app.app_context():
        print("🔧 Initializing chatbot instructions...")
        
        # Default DM instructions
        dm_default = (
            "You are a helpful assistant for our Telegram channel. Be friendly, informative, and respond in the same language the user is using. "
            "Keep responses concise (2-3 sentences) and engaging. Ask clarifying questions when needed. "
            "Provide immediate value. If the user shows interest in premium features, gently mention our paid content."
        )
        
        # Default Channel Comments instructions
        channel_default = (
            "You are responding to a paid comment in the Telegram channel. This user paid Stars (Telegram premium currency) for their comment, "
            "so provide expert-level, detailed responses. Be professional but warm. Acknowledge their question, provide immediate actionable value, "
            "and include examples or specifics. Keep to 2-4 sentences but make every sentence count. "
            "Thank them subtly for their support."
        )
        
        # Save DM instructions
        dm_config = AppConfig.query.filter_by(key='openai_prompt_conversation').first()
        if not dm_config:
            dm_config = AppConfig(
                key='openai_prompt_conversation',
                value=dm_default,
                description='Instructions for AI responses to private messages'
            )
            db.session.add(dm_config)
            print("✓ Created DM instructions")
        else:
            print("✓ DM instructions already exist (skipping)")
        
        # Save Channel instructions
        ch_config = AppConfig.query.filter_by(key='openai_prompt_channel_comments').first()
        if not ch_config:
            ch_config = AppConfig(
                key='openai_prompt_channel_comments',
                value=channel_default,
                description='Instructions for AI responses to paid channel comments'
            )
            db.session.add(ch_config)
            print("✓ Created Channel Comments instructions")
        else:
            print("✓ Channel Comments instructions already exist (skipping)")
        
        db.session.commit()
        
        print("\n✅ Instructions initialized successfully!")
        print("\n📍 You can edit these instructions at: /admin/instructions")
        
        return True

if __name__ == '__main__':
    try:
        init_instructions()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
