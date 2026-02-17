#!/usr/bin/env python
"""Initialize conversation settings and instructions."""
from app import create_app, db
from app.models import AppConfig

app = create_app()

with app.app_context():
    print("=" * 70)
    print("💬 SETTING UP CONVERSATION AI SYSTEM")
    print("=" * 70)
    
    # Default instruction for conversations
    default_prompt = """You are a friendly, knowledgeable, and professional assistant for a Telegram community focused on crypto, technology, and digital innovation.

Your responsibilities:
1. **Be Helpful**: Answer questions clearly and provide useful information
2. **Be Friendly**: Use a warm, conversational tone that builds trust
3. **Be Honest**: If you don't know something, say so. Don't make up information
4. **Be Safe**: Don't promote illegal activities or harmful content
5. **Stay On Topic**: Keep discussions relevant to crypto, tech, and business opportunities
6. **Be Concise**: Keep responses focused and easy to read
7. **Use Emojis Wisely**: Add appropriate emojis to make messages friendly (don't overdo it)
8. **Multilingual**: Respond in the language the user is using

The community's mission:
- Share knowledge about cryptocurrency, blockchain, and Web3
- Discuss investment opportunities and market analysis
- Network with like-minded individuals
- Support members in their crypto journey

Guidelines for responses:
- Always be respectful and professional
- Use simple language, avoid excessive jargon
- When discussing investments, always include risk disclaimers
- Link users to official resources when relevant
- Offer to escalate complex issues to human support if needed
- Remember context from the conversation history
- Personalize responses using the user's name when appropriate

Remember: You're having a continuous conversation with this user. Use the conversation history to understand context and provide coherent, relevant responses."""

    config_key = 'openai_prompt_conversation'
    existing = AppConfig.query.filter_by(key=config_key).first()
    
    if existing:
        print(f"\n⚠️  Instruction already exists")
        print(f"Current: {existing.value[:80]}...")
        update = input("Do you want to update it? (y/n): ").strip().lower()
        if update == 'y':
            existing.value = default_prompt
            existing.description = 'System instruction for AI responses to community members'
            db.session.commit()
            print("✅ Instruction updated")
        else:
            print("ℹ️  Keeping existing instruction")
    else:
        config = AppConfig(
            key=config_key,
            value=default_prompt,
            description='System instruction for AI responses to community members'
        )
        db.session.add(config)
        db.session.commit()
        print("✅ Instruction created")
    
    # Additional voice settings
    config_settings = {
        'voice_message_transcription': ('true', 'Enable voice transcription with Whisper'),
        'conversation_history_limit': ('20', 'Number of previous messages to include in context'),
        'auto_reply_enabled': ('true', 'Enable automatic replies to messages'),
    }
    
    print("\n⚙️  CONFIGURING VOICE & CONVERSATION SETTINGS:")
    
    for key, (value, description) in config_settings.items():
        existing = AppConfig.query.filter_by(key=key).first()
        if existing:
            print(f"  ⚠️  {key} already exists")
        else:
            config = AppConfig(key=key, value=value, description=description)
            db.session.add(config)
            print(f"  ✅ Set {key} = {value}")
    
    db.session.commit()
    
    print("\n" + "=" * 70)
    print("✅ CONVERSATION SYSTEM CONFIGURED!")
    print("=" * 70)
    print("""
Features enabled:
  ✨ Text message support
  🎙️ Voice message transcription (Whisper)
  📁 Audio file support
  💬 Full conversation history
  🧠 Context-aware responses
  🌍 Multilingual support
  
The AI will:
  • Understand user context from conversation history
  • Know who they're talking to (user info)
  • Remember what you've discussed before
  • Respond appropriately based on instructions
  • Handle voice messages and transcribe them

To customize the AI personality:
  1. Go to Admin Panel → OpenAI Settings
  2. Modify "Conversation Instructions"
  3. Save - changes take effect immediately

Next step:
  Run: python telethon_runner.py
  System will start responding to messages!
""")
    print("=" * 70)
