import logging
import os
import tempfile
from datetime import datetime
from telethon import events
from app import db
from app.models import (
    Conversation, ConversationMessage, PaidContent,
    StarTransaction, AppConfig, PublishedPost
)
from app.services.prompt_builder import get_prompt_builder

logger = logging.getLogger(__name__)


class ConversationService:
    _instance = None

    def __init__(self, client_manager, openai_service):
        self.client_manager = client_manager
        self.openai_service = openai_service

    def get_or_create_conversation(self, telegram_user_id, username=None, first_name=None):
        """Get existing or create new conversation."""
        conv = Conversation.query.filter_by(telegram_user_id=telegram_user_id).first()
        if not conv:
            conv = Conversation(
                telegram_user_id=telegram_user_id,
                username=username,
                first_name=first_name
            )
            db.session.add(conv)
            db.session.commit()
        return conv

    def get_conversation_history(self, conversation_id, limit=20):
        """Get recent messages for context - returns list of dicts for OpenAI."""
        messages = ConversationMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(
            ConversationMessage.created_at.asc()
        ).limit(limit).all()

        history = []
        for msg in messages:
            history.append({
                'role': msg.role,
                'content': msg.content
            })

        return history

    def _format_context_for_openai(self, conversation, message_history, user_message):
        """Format conversation context for OpenAI API via PromptBuilder."""
        # Build conversation context text
        context_info = f"User: {conversation.first_name or conversation.username or 'User'} (@{conversation.username or 'unknown'})\n"
        context_info += f"Conversation messages: {conversation.total_messages}\n"
        context_info += f"Status: {'Subscriber' if conversation.is_subscriber else 'Visitor'}\n"
        context_info += f"Language: {conversation.language or 'Unknown'}\n\n"

        if message_history:
            context_info += "Previous messages:\n"
            for msg in message_history[-10:]:
                context_info += f"{msg['role'].upper()}: {msg['content']}\n"

        pb = get_prompt_builder()
        system_prompt = pb.build_system_prompt(
            conversation_context=context_info,
            user_language=conversation.language,
        )

        return system_prompt

    async def generate_response(self, conversation, user_message):
        """Generate AI response using OpenAI with full conversation context."""
        try:
            # Get conversation history
            history = self.get_conversation_history(conversation.id, limit=20)

            # Format context for OpenAI
            system_prompt = self._format_context_for_openai(conversation, history, user_message)

            # Prepare messages for OpenAI API (proper format)
            messages = history.copy()
            messages.append({'role': 'user', 'content': user_message})

            # Use OpenAI chat_with_history to include full dialog + system prompt
            result = self.openai_service.chat_with_history(
                system_prompt=system_prompt,
                messages=messages,
                module='conversation'
            )

            if result and 'content' in result:
                return result['content']
            else:
                return "I'm sorry, I couldn't process that right now. Please try again."

        except Exception as e:
            logger.error(f'Failed to generate response: {e}')
            return "I'm sorry, something went wrong. Please try again later."

    async def transcribe_audio(self, audio_path):
        """Transcribe audio message using OpenAI Whisper."""
        try:
            # Try to use the openai_service if it has transcribe method
            if hasattr(self.openai_service, 'transcribe_audio'):
                text = await self.openai_service.transcribe_audio(audio_path)
                return text
            
            # Fallback: use openai directly
            import openai
            with open(audio_path, 'rb') as audio_file:
                transcript = openai.Audio.transcribe('whisper-1', audio_file)
            return transcript['text']
        
        except Exception as e:
            logger.error(f'Failed to transcribe audio: {e}')
            return None

    async def handle_new_message(self, event):
        """Handle incoming private messages (text and voice)."""
        try:
            sender = await event.get_sender()
            telegram_user_id = sender.id
            username = sender.username
            first_name = sender.first_name

            # Get or create conversation
            conv = self.get_or_create_conversation(telegram_user_id, username, first_name)

            user_message_text = None

            # Handle different message types
            if event.message.text:
                # Regular text message
                user_message_text = event.message.text
                message_type = 'text'
                
            elif event.message.voice:
                # Voice message - transcribe with Whisper
                logger.info(f'Received voice message from {telegram_user_id}')
                
                try:
                    # Download voice message
                    voice_path = await event.message.download_media('app/static/uploads/voice_messages')
                    
                    # Transcribe using Whisper
                    user_message_text = await self.transcribe_audio(voice_path)
                    message_type = 'voice'
                    
                    if user_message_text:
                        logger.info(f'Transcribed voice: {user_message_text[:100]}...')
                    else:
                        await event.reply('Sorry, I couldn\'t understand the voice message. Please send text instead.')
                        return
                        
                    # Clean up voice file
                    if os.path.exists(voice_path):
                        os.remove(voice_path)
                        
                except Exception as e:
                    logger.error(f'Error processing voice message: {e}')
                    await event.reply('Sorry, I had trouble processing your voice message. Please try again.')
                    return
                    
            elif event.message.audio:
                # Audio file - transcribe
                logger.info(f'Received audio file from {telegram_user_id}')
                
                try:
                    audio_path = await event.message.download_media('app/static/uploads/voice_messages')
                    user_message_text = await self.transcribe_audio(audio_path)
                    message_type = 'audio'
                    
                    if user_message_text:
                        logger.info(f'Transcribed audio: {user_message_text[:100]}...')
                    else:
                        await event.reply('Sorry, I couldn\'t understand the audio. Please send text instead.')
                        return
                        
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                        
                except Exception as e:
                    logger.error(f'Error processing audio file: {e}')
                    await event.reply('Sorry, I had trouble processing your audio. Please try again.')
                    return
            else:
                # Unsupported message type
                await event.reply('I can only read text and voice messages. Please send text or voice.')
                return

            if not user_message_text:
                return

            # Save user message
            user_msg = ConversationMessage(
                conversation_id=conv.id,
                role='user',
                content=user_message_text,
                telegram_msg_id=event.message.id
            )
            db.session.add(user_msg)

            # Update conversation metadata
            conv.total_messages += 1
            conv.last_message_at = datetime.utcnow()
            db.session.commit()

            logger.info(f'Received {message_type} from {telegram_user_id}: {user_message_text[:50]}...')

            # Show typing indicator
            async with event.client.action(conv.telegram_user_id, 'typing'):
                # Generate AI response
                response_text = await self.generate_response(conv, user_message_text)

                # Send response
                sent_message = await event.reply(response_text)

                # Save assistant message
                assistant_msg = ConversationMessage(
                    conversation_id=conv.id,
                    role='assistant',
                    content=response_text,
                    telegram_msg_id=sent_message.id
                )
                db.session.add(assistant_msg)
                conv.total_messages += 1
                db.session.commit()

                logger.info(f'Sent response to {telegram_user_id}')

        except Exception as e:
            logger.error(f'Error handling message: {e}', exc_info=True)

    async def handle_channel_comment(self, event):
        """Handle paid comments in channel (replies via swipe left).
        
        When a subscriber replies to a post with a comment (paid):
        - Create conversation record
        - Generate AI response
        - Reply to the comment
        """
        try:
            # This handles messages sent to channel comments
            if not event.is_channel:
                return
            
            sender = await event.get_sender()
            if not sender or sender.is_self:
                return
            
            telegram_user_id = sender.id
            username = sender.username
            first_name = sender.first_name
            
            # Get or create conversation
            conv = self.get_or_create_conversation(telegram_user_id, username, first_name)
            
            # Extract message content
            user_message_text = None
            if event.message.text:
                user_message_text = event.message.text
                message_type = 'comment'
            
            if not user_message_text:
                return
            
            logger.info(f'Channel comment from {telegram_user_id}: {user_message_text[:50]}...')
            
            # Save user message
            user_msg = ConversationMessage(
                conversation_id=conv.id,
                role='user',
                content=user_message_text,
                telegram_msg_id=event.message.id
            )
            db.session.add(user_msg)
            
            # Update conversation
            conv.total_messages += 1
            conv.last_message_at = datetime.utcnow()
            db.session.commit()
            
            # Attempt to detect paid content context (reply to a published post)
            paid_content = None
            try:
                reply_msg = await event.get_reply_message()
                if reply_msg and getattr(reply_msg, 'id', None):
                    # Try to find a PublishedPost matching the replied-to message id
                    published = PublishedPost.query.filter_by(telegram_message_id=reply_msg.id).first()
                    if published:
                        # Try to match a PaidContent by title or source_title
                        paid_content = PaidContent.query.filter(
                            PaidContent.title.ilike(f"%{(published.source_title or '')[:60]}%")
                        ).first()
            except Exception:
                paid_content = None

            # If we found a paid_content with instructions, build a system prompt including it
            if paid_content and (paid_content.instructions or AppConfig.get('openai_prompt_channel_comments')):
                # Build system prompt including paid content instructions
                pb = get_prompt_builder()
                history = self.get_conversation_history(conv.id, limit=20)
                system_prompt = pb.build_system_prompt(
                    conversation_context='\n'.join([f"{m['role']}: {m['content']}" for m in history[-10:]]),
                    paid_instructions=paid_content.instructions,
                    channel_instructions=AppConfig.get('openai_prompt_channel_comments'),
                    user_language=conv.language,
                )
                messages = history.copy()
                messages.append({'role': 'user', 'content': user_message_text})
                result = self.openai_service.chat_with_history(
                    system_prompt=system_prompt,
                    messages=messages,
                    module='conversation'
                )
                response_text = result.get('content') if result else None
            else:
                # Fallback to regular flow
                response_text = await self.generate_response(conv, user_message_text)
            
            # Reply to the comment (by forwarding or sending in thread)
            try:
                sent_message = await event.reply(response_text)
                
                # Save assistant response
                assistant_msg = ConversationMessage(
                    conversation_id=conv.id,
                    role='assistant',
                    content=response_text,
                    telegram_msg_id=sent_message.id
                )
                db.session.add(assistant_msg)
                conv.total_messages += 1
                db.session.commit()
                
                logger.info(f'Replied to channel comment from {telegram_user_id}')
                
            except Exception as e:
                logger.error(f'Failed to reply to channel comment: {e}')
                # Still save the response attempt
                assistant_msg = ConversationMessage(
                    conversation_id=conv.id,
                    role='assistant',
                    content=response_text,
                    telegram_msg_id=None
                )
                db.session.add(assistant_msg)
                db.session.commit()
        
        except Exception as e:
            logger.error(f'Error handling channel comment: {e}', exc_info=True)
        """Approve Telegram Stars payment (pre-checkout query)."""
        try:
            # Always approve (validation can be done here if needed)
            await event.answer(ok=True)
            logger.info(f'Approved pre-checkout for {event.sender_id}')

        except Exception as e:
            logger.error(f'Error in pre-checkout: {e}')
            await event.answer(ok=False, error_message="Payment failed")

    async def handle_successful_payment(self, event):
        """Handle successful Stars payment and deliver content."""
        try:
            telegram_user_id = event.sender_id
            payment = event.payment

            # Get conversation
            conv = self.get_or_create_conversation(telegram_user_id)

            # Parse payment info to find content
            # (This depends on how you structure the payment invoice)
            # For now, assume payload contains content_id
            content_id = int(payment.payload) if payment.payload else None

            if not content_id:
                logger.warning(f'No content_id in payment payload from {telegram_user_id}')
                return

            content = db.session.get(PaidContent, content_id)
            if not content:
                logger.error(f'Content {content_id} not found')
                return

            # Record transaction
            txn = StarTransaction(
                telegram_user_id=telegram_user_id,
                conversation_id=conv.id,
                paid_content_id=content.id,
                amount_stars=content.price_stars,
                telegram_payment_id=payment.charge_id,
                status='completed'
            )
            db.session.add(txn)

            # Update conversation
            conv.total_stars_paid += content.price_stars

            # Update content sales
            content.sales_count += 1

            db.session.commit()

            # Deliver content
            await self.deliver_content(telegram_user_id, content, txn)

            logger.info(f'Payment successful: {telegram_user_id} paid {content.price_stars} stars for {content.title}')

        except Exception as e:
            logger.error(f'Error handling successful payment: {e}', exc_info=True)

    async def deliver_content(self, user_id, content: PaidContent, transaction: StarTransaction):
        """Send the paid content to the user."""
        try:
            client = await self.client_manager.get_client()
            if not client:
                logger.error('No client available for content delivery')
                return

            # Send thank you message
            await client.send_message(
                user_id,
                f"✅ Payment received! Here's your content: **{content.title}**"
            )

            # Send the actual content file
            if content.file_path:
                import os
                full_path = os.path.join('app', 'static', 'uploads', content.file_path)
                if os.path.exists(full_path):
                    await client.send_file(user_id, full_path, caption=content.description or '')

                    # Mark as delivered
                    transaction.content_delivered = True
                    transaction.delivered_at = datetime.utcnow()
                    db.session.commit()

                    logger.info(f'Content delivered to {user_id}')
                else:
                    logger.error(f'File not found: {full_path}')
                    await client.send_message(user_id, "Sorry, the content file is missing. Please contact support.")
            else:
                await client.send_message(user_id, content.description or 'No file attached to this content.')

        except Exception as e:
            logger.error(f'Failed to deliver content to {user_id}: {e}')

    def register_handlers(self, client):
        """Register all Telethon event handlers."""

        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def new_message_handler(event):
            await self.handle_new_message(event)

        logger.info('Conversation event handlers registered')


def get_conversation_service(client_manager=None, openai_service=None):
    """Get or create ConversationService singleton."""
    if ConversationService._instance is None and client_manager and openai_service:
        ConversationService._instance = ConversationService(client_manager, openai_service)
    return ConversationService._instance
