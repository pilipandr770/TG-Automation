import logging
import os
import tempfile
import asyncio
import random
from datetime import datetime
from telethon import events
from app import db
from app.models import (
    Conversation, ConversationMessage, PaidContent,
    StarTransaction, AppConfig, PublishedPost
)
from app.services.prompt_builder import get_prompt_builder
from app.enums import MessageMode

logger = logging.getLogger(__name__)


class ConversationService:
    _instance = None

    def __init__(self, client_manager, openai_service):
        self.client_manager = client_manager
        self.openai_service = openai_service
        self._recent_private_events = {}

    def _prune_recent_private_events(self):
        cutoff = datetime.utcnow().timestamp() - 300
        stale_keys = [key for key, ts in self._recent_private_events.items() if ts < cutoff]
        for key in stale_keys:
            self._recent_private_events.pop(key, None)

    def _is_duplicate_private_event(self, telegram_user_id, message_id, message_text):
        self._prune_recent_private_events()
        key = (telegram_user_id, message_id, (message_text or '')[:120])
        now_ts = datetime.utcnow().timestamp()
        if key in self._recent_private_events:
            return True
        self._recent_private_events[key] = now_ts
        return False

    @staticmethod
    def _should_ignore_private_sender(sender) -> tuple[bool, str]:
        if sender is None:
            return True, 'missing sender'

        if getattr(sender, 'bot', False):
            return True, 'telegram bot account'

        username = (getattr(sender, 'username', None) or '').strip().lower()
        if username in {'combot', 'grouphelpbot', 'botfather', 'manybot', 'controllerbot'}:
            return True, f'ignored service account @{username}'

        return False, ''

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

        logger.debug(f'[HISTORY] Retrieved {len(history)} messages from conversation {conversation_id}')
        return history

    def _format_context_for_openai(self, conversation, message_history, user_message, mode=MessageMode.PRIVATE_DIALOG):
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
            mode=mode,
            conversation_context=context_info,
            user_language=conversation.language,
        )

        return system_prompt

    async def generate_response(self, conversation, user_message):
        """Generate AI response using OpenAI with full conversation context (PRIVATE_DIALOG mode)."""
        try:
            # Recover from any stale/error DB transaction left by a concurrent coordinator step
            try:
                db.session.rollback()
            except Exception:
                pass

            # Get conversation history
            history = self.get_conversation_history(conversation.id, limit=20)

            # Log conversation context for debugging
            logger.info('=' * 70)
            logger.info(f'[CONTEXT] Generating response for user {conversation.telegram_user_id}')
            logger.info(f'[CONTEXT] Conversation history length: {len(history)} messages')
            if history:
                logger.info(f'[CONTEXT] Latest messages in order:')
                for i, msg in enumerate(history[-5:], 1):  # Show last 5 messages
                    role = msg.get('role', 'unknown').upper()
                    content = msg.get('content', '')[:60]
                    logger.info(f'  {i}. [{role}] {content}...')
            logger.info(f'[CONTEXT] New user message: {user_message[:100]}...')
            logger.info('=' * 70)

            # Format context for OpenAI (private dialog mode)
            system_prompt = self._format_context_for_openai(conversation, history, user_message, mode=MessageMode.PRIVATE_DIALOG)

            # Prepare messages for OpenAI API (proper format)
            messages = history.copy()
            messages.append({'role': 'user', 'content': user_message})

            logger.info(f'[OPENAI] Sending {len(messages)} messages to OpenAI (including new user message)')

            # ── All DB work happens HERE in the asyncio coroutine (has app context). ──
            # Only the raw HTTP request goes into run_in_executor.

            # 1) Budget check — uses DB, must stay in asyncio thread
            if not self.openai_service._check_budget():
                logger.warning('[OPENAI] Daily budget exceeded, cannot respond')
                return "I'm sorry, I couldn't process that right now. Please try again."

            # 2) Resolve model name — uses DB, must stay in asyncio thread
            model_name = self.openai_service._get_model()

            # 3) Resolve API key and get client — may use DB for key lookup
            openai_client = self.openai_service.client

            # 4) Build full message list
            full_messages = [{'role': 'system', 'content': system_prompt}] + messages

            # 5) Run ONLY the blocking HTTP call in a thread — zero DB inside
            loop = asyncio.get_running_loop()
            logger.info(f'[OPENAI] Calling API with model={model_name}...')
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: openai_client.chat.completions.create(
                        model=model_name,
                        messages=full_messages,
                        temperature=0.7,
                    )
                )
            except Exception as api_err:
                logger.error(f'[OPENAI] API call failed: {api_err}', exc_info=True)
                return "I'm sorry, I couldn't process that right now. Please try again."

            if not response or not response.choices:
                logger.warning('[OPENAI] Empty response from API')
                return "I'm sorry, I couldn't process that right now. Please try again."

            content = response.choices[0].message.content
            logger.info(f'[OPENAI] Got response ({len(content)} chars)')

            # 6) Log usage — uses DB, back in asyncio thread
            try:
                usage = response.usage
                self.openai_service._log_usage(
                    module='conversation',
                    operation='chat_with_history',
                    model=model_name,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                )
            except Exception as log_err:
                logger.warning(f'[OPENAI] Usage logging failed (non-fatal): {log_err}')

            return content

        except Exception as e:
            logger.error(f'Failed to generate response: {e}')
            return "I'm sorry, something went wrong. Please try again later."

    async def generate_response_for_channel(self, conversation, user_message, paid_instructions=None, channel_instructions=None):
        """Generate AI response for channel comments with explicit mode and instructions.
        
        If paid_instructions are provided, mode is PAID_CHANNEL_REPLY.
        Otherwise, mode is CHANNEL_COMMENT.
        No fallback to generic response - ensures instructions are used.
        """
        try:
            # Determine mode based on whether this is a paid reply
            mode = MessageMode.PAID_CHANNEL_REPLY if paid_instructions else MessageMode.CHANNEL_COMMENT
            
            # Get conversation history
            history = self.get_conversation_history(conversation.id, limit=20)

            # Build system prompt with channel mode
            pb = get_prompt_builder()
            system_prompt = pb.build_system_prompt(
                mode=mode,
                conversation_context='\n'.join([f"{m['role']}: {m['content']}" for m in history[-10:]]),
                paid_instructions=paid_instructions,
                channel_instructions=channel_instructions,
                user_language=conversation.language,
            )

            # Prepare messages for OpenAI
            messages = history.copy()
            messages.append({'role': 'user', 'content': user_message})

            # ── All DB work in asyncio coroutine; only HTTP in executor ──

            # Budget check
            if not self.openai_service._check_budget():
                logger.warning('[OPENAI] Daily budget exceeded for channel response')
                return None

            model_name = self.openai_service._get_model()
            openai_client = self.openai_service.client
            full_messages = [{'role': 'system', 'content': system_prompt}] + messages

            loop = asyncio.get_running_loop()
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: openai_client.chat.completions.create(
                        model=model_name,
                        messages=full_messages,
                        temperature=0.7,
                    )
                )
            except Exception as api_err:
                logger.error(f'[CHANNEL RESPONSE] API call failed: {api_err}', exc_info=True)
                return None

            if not response or not response.choices:
                logger.warning(f'[CHANNEL RESPONSE] Empty response from OpenAI (mode={mode.value})')
                return None

            response_text = response.choices[0].message.content
            logger.info(f'[CHANNEL RESPONSE] Generated {mode.value} response ({len(response_text)} chars)')

            try:
                usage = response.usage
                self.openai_service._log_usage(
                    module='conversation',
                    operation='chat_with_history',
                    model=model_name,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                )
            except Exception as log_err:
                logger.warning(f'[CHANNEL RESPONSE] Usage logging failed (non-fatal): {log_err}')

            return response_text

        except Exception as e:
            logger.error(f'[CHANNEL RESPONSE] Failed to generate {mode.value} response: {e}', exc_info=True)
            return None

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
            # Log incoming message
            logger.info(f'[MESSAGE] Incoming message event received: {event}')
            
            sender = await event.get_sender()
            telegram_user_id = sender.id
            username = sender.username
            first_name = sender.first_name

            ignore_sender, ignore_reason = self._should_ignore_private_sender(sender)
            if ignore_sender:
                logger.info(f'[MESSAGE SKIP] Ignoring private message from {telegram_user_id}: {ignore_reason}')
                return
            
            logger.info(f'[MESSAGE] From user {telegram_user_id} ({username}, {first_name})')

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

            if self._is_duplicate_private_event(telegram_user_id, event.message.id, user_message_text):
                logger.info(f'[MESSAGE SKIP] Duplicate private event ignored for {telegram_user_id} message_id={event.message.id}')
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

            # Add random delay to make responses look natural (configurable)
            # Defaults are intentionally moderate for better UX in private chat.
            delay_min = float(os.getenv('DM_REPLY_DELAY_MIN_SECONDS', '3'))
            delay_max = float(os.getenv('DM_REPLY_DELAY_MAX_SECONDS', '15'))
            if delay_max < delay_min:
                delay_min, delay_max = delay_max, delay_min

            delay_seconds = random.uniform(delay_min, delay_max)
            logger.info(
                f'⏰ [DELAY] Adding {delay_seconds:.1f}s delay before response '
                f'(range: {delay_min:.1f}-{delay_max:.1f}s)'
            )

            # Show typing indicator during delay + generation so user sees activity immediately
            logger.info(f'[DM REPLY] Starting typing + response flow for {telegram_user_id}')
            async with event.client.action(conv.telegram_user_id, 'typing'):
                await asyncio.sleep(delay_seconds)
                logger.info(f'⏰ [DELAY] Delay complete, now generating response...')
                # Generate AI response
                response_text = await self.generate_response(conv, user_message_text)

                # Telegram hard limit — truncate to avoid MessageTooLongError
                MAX_TG_LEN = 4096
                if response_text and len(response_text) > MAX_TG_LEN:
                    logger.warning(f'[DM REPLY] Response truncated {len(response_text)} → {MAX_TG_LEN} chars')
                    response_text = response_text[:MAX_TG_LEN - 3] + '...'

                # Send response — isolated so DB errors don't block the reply
                sent_message = None
                logger.info(f'[DM REPLY] Sending reply to {telegram_user_id} ({len(response_text)} chars)...')
                try:
                    sent_message = await event.reply(response_text)
                    logger.info(f'✅ Sent response to {telegram_user_id} (msg_id={sent_message.id})')
                except Exception as reply_err:
                    logger.error(f'[DM REPLY] Failed to send reply to {telegram_user_id}: {reply_err}', exc_info=True)

                # Save assistant message regardless of send result
                try:
                    assistant_msg = ConversationMessage(
                        conversation_id=conv.id,
                        role='assistant',
                        content=response_text,
                        telegram_msg_id=sent_message.id if sent_message else None
                    )
                    db.session.add(assistant_msg)
                    conv.total_messages += 1
                    db.session.commit()
                except Exception as db_err:
                    logger.error(f'[DM REPLY] DB save failed for {telegram_user_id}: {db_err}')

        except Exception as e:
            logger.error(f'Error handling message: {e}', exc_info=True)

    async def handle_channel_comment(self, event):
        """Handle comments/replies in the configured target channel only.

        Only responds when:
        - The event is from the target channel configured in AppConfig
        - The message is a reply (reply_to_msg_id is set) — i.e. a comment on a post
        - The sender is a real user (not the channel itself)

        IMPORTANT: Do NOT fallback to generic response. Use explicit modes.
        """
        try:
            # ── Guard 1: only target channel ────────────────────────────
            target_channel = AppConfig.get('target_channel', '').strip()
            if not target_channel:
                return  # No target configured — don't respond to any channel messages

            try:
                if target_channel.lstrip('-').isdigit():
                    if str(event.chat_id) != target_channel:
                        return
                else:
                    chat = await event.get_chat()
                    chat_username = (getattr(chat, 'username', None) or '').lower()
                    if chat_username != target_channel.lstrip('@').lower():
                        return
            except Exception:
                return  # Can't confirm channel, skip to be safe

            # ── Guard 2: only replies (comments), not standalone posts ──
            if not event.reply_to_msg_id:
                return

            # ── Guard 3: sender must be a real user ─────────────────────
            if not event.sender_id or event.sender_id < 0:
                return  # channel/anonymous post, not a user comment

            # For channel messages, use sender_id directly (not get_sender which returns Channel object)
            telegram_user_id = event.sender_id
            
            # Try to get sender details if available
            try:
                sender = await event.get_sender()
                # Only use sender if it's a User, not a Channel
                if hasattr(sender, 'first_name'):
                    username = getattr(sender, 'username', None)
                    first_name = getattr(sender, 'first_name', None)
                else:
                    # Fallback for Channel objects
                    username = None
                    first_name = None
            except Exception as sender_err:
                logger.debug(f'Could not get sender details: {sender_err}')
                username = None
                first_name = None
            
            # Get or create conversation
            conv = self.get_or_create_conversation(telegram_user_id, username, first_name)
            
            # Extract message content
            user_message_text = None
            if event.message.text:
                user_message_text = event.message.text
                message_type = 'comment'
            
            if not user_message_text:
                return
            
            logger.info(f'[CHANNEL COMMENT] Received from {telegram_user_id}: {user_message_text[:50]}...')
            
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
                        if paid_content:
                            logger.info(f'[CHANNEL COMMENT] Detected paid content reply: {paid_content.id}')
            except Exception as e:
                logger.debug(f'[CHANNEL COMMENT] Could not detect paid content: {e}')
                paid_content = None

            # Generate response with explicit mode
            # If paid_content detected, use paid instructions; otherwise use channel instructions
            paid_instructions = paid_content.instructions if paid_content else None
            channel_instructions = AppConfig.get('openai_prompt_channel_comments')
            
            logger.info(f'[CHANNEL COMMENT] Calling OpenAI for response (paid={paid_content is not None}, has_channel_instructions={bool(channel_instructions)})...')
            response_text = await self.generate_response_for_channel(
                conv,
                user_message_text,
                paid_instructions=paid_instructions,
                channel_instructions=channel_instructions
            )
            logger.info(f'[CHANNEL COMMENT] OpenAI call returned: {repr(response_text[:80]) if response_text else None}')
            
            # FORBID fallback - if response_text is None, abort
            if not response_text:
                logger.error(f'[CHANNEL COMMENT] Failed to generate response, aborting reply')
                return
            
            # Reply to the comment with Topics channel support
            sent_message = None
            try:
                # Attempt 1: Use event.reply() which handles Topics automatically
                logger.info(f'[CHANNEL REPLY] Attempting reply via event.reply()...')
                sent_message = await event.reply(response_text)
                logger.info(f'[CHANNEL REPLY] Successfully replied to {message_type} from {telegram_user_id}')
                
            except Exception as reply_err:
                # Attempt 2: If Topics error, try sending directly to topic
                if 'MONOFORUM' in str(reply_err) or 'REPLY_TO_MONOFORUM' in str(reply_err):
                    logger.info(f'[CHANNEL REPLY] Topics/Forum channel detected, using topic-aware send...')
                    try:
                        # For Topics channels, send as regular message to the topic
                        # event.reply() with edit_reply=False should work for topics
                        chat_entity = await event.client.get_entity(event.chat_id)
                        
                        # Check if message has topic_id (Forums feature)
                        topic_id = getattr(event.message, 'topic_id', None)
                        if topic_id:
                            logger.info(f'[CHANNEL REPLY] Message from topic {topic_id}, sending to topic...')
                            # Send to specific topic (no reply_to)
                            sent_message = await event.client.send_message(
                                chat_entity,
                                response_text,
                                reply_to=None,
                                comment_to=topic_id if hasattr(event.message, 'is_topic') else None
                            )
                        else:
                            # No topic ID, send as plain message
                            logger.info(f'[CHANNEL REPLY] Sending as plain message to channel...')
                            sent_message = await event.client.send_message(
                                chat_entity,
                                response_text
                            )
                        
                        logger.info(f'[CHANNEL REPLY] Successfully sent to Topics/Forum channel from {telegram_user_id}')
                    
                    except Exception as topic_err:
                        logger.error(f'[CHANNEL REPLY] Topic-aware send also failed: {topic_err}', exc_info=True)
                        # FINAL FALLBACK: Try with highest-level API
                        try:
                            logger.info(f'[CHANNEL REPLY] Attempting final fallback via direct client send...')
                            sent_message = await event.client.send_message(event.chat_id, response_text)
                            logger.info(f'[CHANNEL REPLY] Final fallback succeeded')
                        except Exception as final_err:
                            logger.error(f'[CHANNEL REPLY] All send attempts failed: {final_err}', exc_info=True)
                else:
                    logger.error(f'[CHANNEL REPLY] Failed to send reply: {reply_err}', exc_info=True)

            # Always save assistant response — whether send succeeded or failed
            assistant_msg = ConversationMessage(
                conversation_id=conv.id,
                role='assistant',
                content=response_text,
                telegram_msg_id=sent_message.id if sent_message else None
            )
            db.session.add(assistant_msg)
            conv.total_messages += 1
            db.session.commit()
            if sent_message:
                logger.info(f'[CHANNEL REPLY] Response saved (msg_id={sent_message.id})')
            else:
                logger.warning('[CHANNEL REPLY] Response saved without message_id (send failed)')
        
        except Exception as e:
            logger.error(f'[CHANNEL COMMENT] Error handling channel comment: {e}', exc_info=True)

    async def handle_pre_checkout_query(self, event):
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
            logger.info(f'[HANDLER] PRIVATE MESSAGE EVENT TRIGGERED!')
            logger.info(f'[HANDLER] Event class: {event.__class__.__name__}')
            logger.info(f'[HANDLER] Is private: {event.is_private}')
            logger.info(f'[HANDLER] Has text: {event.message.text is not None}')
            try:
                await self.handle_new_message(event)
            except Exception as e:
                logger.error(f'[HANDLER] Error in handle_new_message: {e}', exc_info=True)

        # Handle replies to channel posts (comments via swipe-left)
        @client.on(events.NewMessage(incoming=True, func=lambda e: not e.is_private and (e.is_channel or e.is_group)))
        async def channel_comment_handler(event):
            logger.info(f'[HANDLER] CHANNEL/GROUP MESSAGE EVENT TRIGGERED!')
            logger.info(f'[HANDLER] Is channel: {event.is_channel}')
            logger.info(f'[HANDLER] Is group: {event.is_group}')
            logger.info(f'[HANDLER] Reply to: {event.reply_to_msg_id}')
            try:
                await self.handle_channel_comment(event)
            except Exception as e:
                logger.error(f'[HANDLER] Error in handle_channel_comment: {e}', exc_info=True)

        logger.info('Conversation event handlers registered - listening for private messages and channel replies')


def get_conversation_service(client_manager=None, openai_service=None):
    """Get or create ConversationService singleton."""
    if ConversationService._instance is None and client_manager and openai_service:
        ConversationService._instance = ConversationService(client_manager, openai_service)
    return ConversationService._instance
