#!/usr/bin/env python
"""Check conversation system status."""
from app import create_app, db
from app.models import Conversation, ConversationMessage, AppConfig

app = create_app()

with app.app_context():
    print("=" * 70)
    print("💬 CONVERSATION SYSTEM STATUS")
    print("=" * 70)
    
    # Check configuration
    print("\n⚙️ SYSTEM CONFIGURATION:")
    
    configs = {
        'openai_prompt_conversation': 'AI Instruction',
        'voice_message_transcription': 'Voice Support',
        'conversation_history_limit': 'Context Window',
        'auto_reply_enabled': 'Auto Reply',
    }
    
    for key, label in configs.items():
        config = AppConfig.query.filter_by(key=key).first()
        if config:
            preview = config.value[:50] + '...' if len(config.value) > 50 else config.value
            print(f"  ✅ {label}: {preview}")
        else:
            print(f"  ❌ {label}: NOT CONFIGURED")
    
    # Check conversations
    print("\n👥 ACTIVE CONVERSATIONS:")
    
    convs = Conversation.query.all()
    print(f"  Total conversations: {len(convs)}")
    
    if convs:
        for conv in convs[:5]:
            print(f"\n  - {conv.first_name or conv.username or 'Unknown'}:")
            print(f"    Messages: {conv.total_messages}")
            print(f"    Subscriber: {conv.is_subscriber}")
            print(f"    Last message: {conv.last_message_at}")
    
    if len(convs) > 5:
        print(f"\n  ... and {len(convs) - 5} more conversations")
    
    # Check recent messages
    print("\n💬 RECENT MESSAGES:")
    
    recent = ConversationMessage.query.order_by(
        ConversationMessage.created_at.desc()
    ).limit(5).all()
    
    for msg in reversed(recent):
        conv = Conversation.query.get(msg.conversation_id)
        user = conv.first_name or conv.username or 'Unknown'
        role_icon = "👤" if msg.role == 'user' else "🤖"
        content = msg.content[:50] + '...' if len(msg.content) > 50 else msg.content
        print(f"  {role_icon} {user}: {content}")
    
    if not recent:
        print("  ℹ️ No messages yet - waiting for users to write...")
    
    print("\n" + "=" * 70)
    print("🚀 READY TO RESPOND TO MESSAGES!")
    print("=" * 70)
    
    if not convs:
        print("\nℹ️ No conversations yet. When someone writes you a message:")
        print("  1. The system will create a conversation")
        print("  2. AI will analyze context and instructions")
        print("  3. Auto-reply will be sent back")
        print("  4. Full conversation history will be saved")
    
    print("\nFeatures:")
    print("  ✅ Text messages")
    print("  ✅ Voice transcription (Whisper)")
    print("  ✅ Audio files")
    print("  ✅ Full conversation context")
    print("  ✅ Personalized responses")
    print("  ✅ Multi-language support")
    
    print("\nRun: python telethon_runner.py")
    print("=" * 70)
