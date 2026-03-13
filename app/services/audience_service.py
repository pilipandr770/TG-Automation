"""
Audience Service — Module 2: Target Audience.

Scans messages in joined channels, pre-filters by keywords, then uses
OpenAI to evaluate whether a user matches the target audience criteria.
"""

import asyncio
import json
import logging
import re
from datetime import datetime

from telethon import functions, types
from telethon.errors import FloodWaitError, ChannelPrivateError
from telethon.tl.types import InputPeerChannel

logger = logging.getLogger(__name__)


class AudienceService:
    """Identifies target-audience contacts by scanning joined channels."""

    _instance = None

    def __init__(self):
        from app.services.telegram_client import get_telegram_client_manager
        from app.services.rate_limiter import get_rate_limiter
        from app.services.openai_service import get_openai_service

        self._client_manager = get_telegram_client_manager()
        self._rate_limiter = get_rate_limiter()
        self._openai = get_openai_service()

    # ── config helpers ───────────────────────────────────────────────────

    def _get_scan_interval(self) -> int:
        try:
            from app.models import AppConfig
            # Default 600 seconds (10 min) for continuous operation, can be overridden in config
            value = AppConfig.get('audience_scan_interval')
            if value is not None:
                return int(value)

            minutes = AppConfig.get('audience_scan_interval_minutes')
            if minutes is not None:
                return int(minutes) * 60

            return 600
        except (TypeError, ValueError):
            return 600

    def _get_message_scan_limit(self) -> int:
        try:
            from app.models import AppConfig

            value = AppConfig.get('audience_message_limit')
            if value is not None:
                return max(50, min(int(value), 500))
            return 150
        except (TypeError, ValueError):
            return 150

    def _get_analysis_cap_per_channel(self) -> int:
        try:
            from app.models import AppConfig

            value = AppConfig.get('audience_analysis_cap_per_channel')
            if value is not None:
                return max(10, min(int(value), 100))
            return 30
        except (TypeError, ValueError):
            return 30

    async def _save_contact_to_telegram_profile(self, msg_data: dict) -> bool:
        """Best-effort save of a newly discovered target contact into Telegram contacts."""
        client = await self._client_manager.get_client()
        if client is None:
            logger.warning('[CONTACT SAVE] No Telegram client available')
            return False

        try:
            if msg_data.get('access_hash'):
                input_user = types.InputUser(msg_data['user_id'], msg_data['access_hash'])
            elif msg_data.get('username'):
                username = msg_data['username']
                peer_ref = username if username.startswith('@') else f'@{username}'
                input_user = await client.get_input_entity(peer_ref)
            else:
                logger.info('[CONTACT SAVE] Skipping Telegram contact save for %s: no username/access_hash', msg_data.get('user_id'))
                return False

            first_name = (msg_data.get('first_name') or msg_data.get('username') or 'Telegram')[:64]
            last_name = (msg_data.get('last_name') or '')[:64]

            await client(functions.contacts.AddContactRequest(
                id=input_user,
                first_name=first_name,
                last_name=last_name,
                phone=''.join(ch for ch in (msg_data.get('phone') or '') if ch.isdigit() or ch == '+'),
                add_phone_privacy_exception=False,
            ))
            logger.info('[CONTACT SAVE] Added contact %s to Telegram profile', msg_data.get('user_id'))
            return True
        except Exception as e:
            logger.warning('[CONTACT SAVE] Failed to add %s to Telegram profile: %s', msg_data.get('user_id'), str(e)[:150])
            return False

    # ── core methods ─────────────────────────────────────────────────────

    async def scan_channel_messages(
        self, channel_id: int, limit: int = 500, username: str = None
    ) -> list[dict]:
        """Read recent messages from a joined channel (last 500 messages ~ 5-10 days).

        Returns a list of dicts: {user_id, username, first_name, last_name,
        message_text, message_id}.
        """
        client = await self._client_manager.get_client()
        if client is None:
            logger.warning('[SCAN] No client available for channel %s', channel_id)
            return []

        if not await self._rate_limiter.acquire('read_messages'):
            logger.warning('[SCAN] Rate limited — skipping message scan for channel %s', channel_id)
            return []

        results = []
        
        # Try to fetch messages using username if available (more reliable)
        # Fall back to ID if no username
        channel_ref = f'@{username}' if username else channel_id
        
        logger.info(f'[SCAN] Attempting to fetch messages from {channel_ref} (limit={limit})')
        
        try:
            messages = await client.get_messages(channel_ref, limit=limit)
            logger.info(f'[SCAN] Successfully fetched {len(messages)} messages from {channel_ref}')
        except FloodWaitError as e:
            logger.warning(f'[SCAN] FloodWait on {channel_ref}: {e}')
            await self._rate_limiter.handle_flood_wait(e)
            return []
        except ChannelPrivateError:
            logger.warning(f'[SCAN] Channel {channel_id} is private or we were kicked')
            return []
        except Exception as e:
            logger.warning(f'[SCAN] Failed to fetch messages from channel {channel_id}: {str(e)[:100]}')
            return []

        # Process messages one by one, skip any with errors
        skipped_no_text = 0
        skipped_no_sender = 0
        skipped_not_user = 0
        skipped_bots = 0
        
        for msg in messages:
            try:
                if not msg.text:
                    skipped_no_text += 1
                    continue
                if not msg.sender:
                    skipped_no_sender += 1
                    continue
                sender = msg.sender
                if not isinstance(sender, types.User):
                    skipped_not_user += 1
                    continue
                # Skip bots
                if getattr(sender, 'bot', False):
                    skipped_bots += 1
                    continue

                results.append({
                    'user_id': sender.id,
                    'access_hash': getattr(sender, 'access_hash', None),
                    'username': sender.username,
                    'first_name': getattr(sender, 'first_name', '') or '',
                    'last_name': getattr(sender, 'last_name', '') or '',
                    'message_text': msg.text,
                    'message_id': msg.id,
                })
            except Exception as e:
                # Skip individual messages with issues, continue with next message
                logger.debug('[SCAN] Skipping message in channel %s: %s', channel_id, str(e)[:80])
                continue

        logger.info(f'[SCAN] Processed messages from {channel_ref}: {len(results)} users extracted (skipped: {skipped_no_text} no text, {skipped_no_sender} no sender, {skipped_not_user} not user, {skipped_bots} bots)')
        return results

    def _pre_filter(self, message_text: str, criteria) -> bool:
        """Quick keyword check before calling OpenAI.

        Returns True if the message contains at least one keyword from
        the criteria's keyword list.
        """
        if not criteria.keywords:
            # No keywords configured — send everything to AI
            return True

        keywords = [k.strip().lower() for k in criteria.keywords.split(',') if k.strip()]
        text_lower = (message_text or '').lower()

        for keyword in keywords:
            # Use word-aware matching so short keywords like "ton" do not match
            # unrelated words such as "tonight".
            pattern = r'(?<!\w)' + re.escape(keyword) + r'(?!\w)'
            if re.search(pattern, text_lower, flags=re.IGNORECASE):
                return True

        return False

    async def analyze_user(
        self,
        user_entity: dict,
        message_text: str,
        criteria,
    ) -> dict:
        """Categorize user and check if matches target audience.

        Returns: {
            category: 'admin'|'competitor'|'bot'|'promoter'|'spam'|'target_audience',
            match: bool,
            confidence: float,
            reason: str
        }
        """
        # Step 1: Validate inputs and handle None values
        if message_text is None:
            message_text = ''
        message_text = str(message_text).strip()
        
        username = user_entity.get('username') or ''
        username = str(username).lower() if username else ''
        first_name = user_entity.get('first_name') or ''
        first_name = str(first_name).lower() if first_name else ''
        
        logger.debug(f'[ANALYZE USER] @{username} ({first_name}): "{message_text[:60]}..."')
        
        # Check if likely a bot (by username patterns or indicators)
        bot_indicators = ['bot', 'автобот', 'робот', 'spam', 'click', 'like']
        if any(ind in username for ind in bot_indicators) or any(ind in first_name for ind in bot_indicators):
            logger.debug(f'[BOT DETECTED] @{username} - contains bot indicator')
            return {
                'category': 'bot',
                'match': False,
                'confidence': 0.95,
                'reason': 'Bot detected by name pattern'
            }
        
        # Step 2: Analyze message to detect category
        system_prompt_categorize = (
            'You are an audience categorizer. Analyze the user message and categorize them.\n'
            'Categories:\n'
            '- admin: Channel owner, moderator, or staff\n'
            '- competitor: Competitor business or same niche competitor\n'
            '- promoter: Promoter, marketing, affiliate, network marketer\n'
            '- spam: Scammer, spam, low-quality content\n'
            '- target_audience: Regular user matching target audience\n\n'
            'Reply in JSON: {"category": "...", "confidence": 0.0-1.0, "reason": "..."}'
        )
        
        user_msg_categorize = (
            f'User: {first_name} (@{username})\n'
            f'Message: {message_text[:500]}'
        )
        
        logger.debug(f'[OPENAI QUERY] Categorizing @{username}: {user_msg_categorize[:100]}...')

        # Run blocking OpenAI call in executor to avoid freezing the Telethon event loop.
        _loop = asyncio.get_running_loop()
        ai_category = await _loop.run_in_executor(
            None,
            lambda: self._openai.chat(
                system_prompt=system_prompt_categorize,
                user_message=user_msg_categorize,
                module='audience_categorize',
            )
        )
        
        category = 'target_audience'
        category_confidence = 0.5
        category_reason = 'Default categorization'
        
        if ai_category.get('content'):
            try:
                content = ai_category['content'].strip()
                logger.debug(f'[OPENAI RESPONSE] Raw: {content}')
                if content:  # Only parse if non-empty
                    parsed = json.loads(content)
                    category = parsed.get('category', 'target_audience')
                    category_confidence = float(parsed.get('confidence', 0.5))
                    category_reason = str(parsed.get('reason', ''))
                    logger.info(f'[CATEGORIZED] @{username} → {category} ({category_confidence:.2f})')
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(f'Could not parse category AI response: {e} | Response: {repr(ai_category.get("content"))}')
        else:
            logger.warning(f'[OPENAI ERROR] No content in categorization response for @{username}')
        
        # Step 3: If NOT target_audience, return immediately
        if category != 'target_audience':
            logger.debug(f'[SKIP ANALYZE] @{username} is {category}, not analyzing further')
            return {
                'category': category,
                'match': False,
                'confidence': category_confidence,
                'reason': category_reason
            }

        logger.info(
            '[MATCH RESULT] @%s treated as target_audience with confidence=%.2f for criteria "%s"',
            username,
            category_confidence,
            criteria.name,
        )
        return {
            'category': 'target_audience',
            'match': True,
            'confidence': category_confidence,
            'reason': category_reason,
        }

    async def run_audience_scan(self) -> dict:
        """One full audience scan across all joined channels.

        Categorizes users and only saves target_audience contacts.
        Returns summary dict with counts.
        """
        from app import db
        from app.models import DiscoveredChannel, AudienceCriteria, Contact

        stats = {
            'channels_scanned': 0,
            'messages_read': 0,
            'users_analyzed': 0,
            'admins_found': 0,
            'competitors_found': 0,
            'bots_found': 0,
            'promoters_found': 0,
            'spam_found': 0,
            'target_audience_found': 0,
            'saved_contacts': 0,
        }

        logger.info('\n' + '=' * 70)
        logger.info('[AUDIENCE SCAN START] Querying joined channels from database...')
        logger.info('=' * 70)
        
        channels = DiscoveredChannel.query.filter_by(
            is_joined=True, is_blacklisted=False
        ).all()
        
        logger.info(f'✅ [QUERY RESULT] Found {len(channels)} joined channels in database')
        if channels:
            for ch in channels[:5]:  # Show first 5
                logger.info(f'  - {ch.title} ({ch.telegram_id})')
            if len(channels) > 5:
                logger.info(f'  ... and {len(channels) - 5} more')

        criteria_list = AudienceCriteria.query.filter_by(active=True).all()
        logger.info(f'✅ [CRITERIA RESULT] Found {len(criteria_list)} active audience criteria')
        if criteria_list:
            for crit in criteria_list:
                keywords = crit.keywords or '(no keywords)'
                logger.info(f'  📋 Criteria: "{crit.name}"')
                logger.info(f'     ├─ Keywords: {keywords}')
                logger.info(f'     ├─ Min confidence: {crit.min_confidence}')
                logger.info(f'     └─ Status: active')
        else:
            logger.warning('⚠️  [NO CRITERIA] No active audience criteria found!')
        
        if not criteria_list:
            logger.info('⚠️  [SKIP] No active audience criteria — skipping scan')
            logger.info('=' * 70)
            return stats
        
        if not channels:
            logger.info('⚠️  [SKIP] No joined channels — skipping scan')
            logger.info('=' * 70)
            return stats
        
        logger.info(f'\n✅ [READY] Starting scan of {len(channels)} channels with {len(criteria_list)} criteria...')

        message_limit = self._get_message_scan_limit()
        analysis_cap_per_channel = self._get_analysis_cap_per_channel()
        logger.info(f'[AUDIENCE CONFIG] message_limit={message_limit}, analysis_cap_per_channel={analysis_cap_per_channel}')

        for channel in channels:
            logger.info(f'\n[SCAN CHANNEL] Scanning: {channel.title} ({channel.telegram_id})')
            messages = await self.scan_channel_messages(
                channel.telegram_id,
                limit=message_limit,
                username=channel.username,
            )
            stats['channels_scanned'] += 1
            stats['messages_read'] += len(messages)
            
            logger.info(f'[SCAN CHANNEL] Read {len(messages)} messages from {channel.title or channel.telegram_id}')
            
            if not messages:
                logger.info(f'[SCAN CHANNEL] No messages found in {channel.title}')
                channel.last_scanned_at = datetime.utcnow()
                continue

            # Update last scanned
            channel.last_scanned_at = datetime.utcnow()
            
            pre_filter_passed = 0
            users_processed = 0
            analyzed_in_channel = 0
            seen_user_ids = set()  # Avoid analyzing the same user multiple times in one channel scan

            for msg_data in messages:
                user_id = msg_data['user_id']
                username = msg_data.get('username') or msg_data.get('first_name') or f'ID{user_id}'
                users_processed += 1

                # Skip if already seen in this scan cycle (user had multiple messages)
                if user_id in seen_user_ids:
                    continue
                seen_user_ids.add(user_id)

                # Skip already-known contacts
                existing = Contact.query.filter_by(telegram_id=user_id).first()
                if existing:
                    updated = False
                    if not existing.access_hash and msg_data.get('access_hash'):
                        existing.access_hash = msg_data.get('access_hash')
                        updated = True
                    if not existing.username and msg_data.get('username'):
                        existing.username = msg_data.get('username')
                        updated = True
                    if not existing.first_name and msg_data.get('first_name'):
                        existing.first_name = msg_data.get('first_name')
                        updated = True
                    if not existing.last_name and msg_data.get('last_name'):
                        existing.last_name = msg_data.get('last_name')
                        updated = True
                    if updated:
                        logger.info(f'[CONTACT UPDATE] Refreshed peer data for existing contact {existing.id} ({user_id})')
                        await self._save_contact_to_telegram_profile(msg_data)
                    continue

                for criteria in criteria_list:
                    if analyzed_in_channel >= analysis_cap_per_channel:
                        logger.info(
                            '[CHANNEL CAP] Reached analysis cap for %s: %s users analyzed',
                            channel.title,
                            analysis_cap_per_channel,
                        )
                        break

                    # Pre-filter
                    pre_filter_result = self._pre_filter(msg_data['message_text'], criteria)
                    
                    if not pre_filter_result:
                        logger.debug(f'[PRE-FILTER REJECT] @{username} - keywords not matched for criteria "{criteria.name}"')
                        continue
                    
                    pre_filter_passed += 1
                    logger.info(f'[PRE-FILTER PASS] @{username} passed criteria "{criteria.name}"')
                    logger.info(f'[ANALYZING] User @{username} - Message: {msg_data["message_text"][:80]}...')
                    
                    # Analyze and categorize
                    evaluation = await self.analyze_user(
                        msg_data, msg_data['message_text'], criteria
                    )
                    stats['users_analyzed'] += 1
                    analyzed_in_channel += 1
                    logger.info(f'[ANALYSIS RESULT] Category: {evaluation.get("category")}, Confidence: {evaluation.get("confidence", 0):.2f}')

                    # Track all categories
                    category = evaluation.get('category', 'target_audience')
                    if category == 'admin':
                        stats['admins_found'] += 1
                    elif category == 'competitor':
                        stats['competitors_found'] += 1
                    elif category == 'bot':
                        stats['bots_found'] += 1
                    elif category == 'promoter':
                        stats['promoters_found'] += 1
                    elif category == 'spam':
                        stats['spam_found'] += 1
                    elif category == 'target_audience':
                        stats['target_audience_found'] += 1

                    # Only save target_audience contacts that match criteria
                    if category != 'target_audience':
                        logger.debug(f'Skipping {category} contact: {msg_data.get("username")}')
                        break  # Move to next user

                    # For target_audience, just check confidence threshold
                    # Skip the secondary matching - categorization is sufficient
                    if evaluation.get('confidence', 0.0) < criteria.min_confidence:
                        logger.info(f'[LOW CONFIDENCE] Skipping {msg_data.get("username")} ({evaluation.get("confidence", 0):.2f} < {criteria.min_confidence})')
                        continue

                    logger.info(f'✅ [SAVED] Added contact: @{msg_data.get("username", user_id)}')
                    stats['saved_contacts'] += 1

                    contact = Contact(
                        telegram_id=user_id,
                        access_hash=msg_data.get('access_hash'),
                        username=msg_data.get('username'),
                        first_name=msg_data.get('first_name'),
                        last_name=msg_data.get('last_name'),
                        confidence_score=evaluation.get('confidence', 0.0),
                        analysis_summary=evaluation.get('reason', '')[:500],
                        source_channel_id=channel.id,
                        source_message_text=msg_data['message_text'][:1000],
                        criteria_id=criteria.id,
                        category='target_audience',
                        status='identified',
                    )
                    db.session.add(contact)
                    await self._save_contact_to_telegram_profile(msg_data)
                    # Only match once per user — break criteria loop
                    break

                if analyzed_in_channel >= analysis_cap_per_channel:
                    break

            db.session.commit()
            
            # Show pre-filter stats for this channel
            logger.info(f'\n[CHANNEL STATS] {channel.title}:')
            logger.info(f'  📊 Total messages: {len(messages)}')
            logger.info(f'  👥 Unique users: {users_processed}')
            logger.info(f'  ✅ Passed pre-filter: {pre_filter_passed}')
            logger.info(f'  📝 Analyzed: {stats["users_analyzed"]}')
            logger.info(f'  💾 Saved contacts: {stats["saved_contacts"]}')
            
            # Small delay between channels
            await asyncio.sleep(1)

        logger.info('=' * 70)
        logger.info(f'[AUDIENCE SCAN COMPLETE] Results: {stats}')
        logger.info('=' * 70)
        return stats

    async def run_forever(self) -> None:
        """Run audience scans in an infinite loop."""
        logger.info('=' * 70)
        logger.info('[AUDIENCE] Starting infinite loop - will scan joined channels regularly')
        logger.info('=' * 70)
        
        cycle_count = 0
        while True:
            cycle_count += 1
            interval = self._get_scan_interval()
            logger.info(f'\n[AUDIENCE CYCLE START] Cycle #{cycle_count}')
            
            try:
                stats = await self.run_audience_scan()
                logger.info('=' * 70)
                logger.info(f'[AUDIENCE CYCLE COMPLETE] Stats: {stats}')
                logger.info('=' * 70)
            except Exception as e:
                logger.error(f'[AUDIENCE ERROR] Scan failed: {type(e).__name__}: {str(e)[:150]}', exc_info=True)

            logger.info(f'[AUDIENCE] Waiting {interval} seconds until next scan...')
            await asyncio.sleep(interval)


# ── Singleton accessor ───────────────────────────────────────────────────

def get_audience_service() -> AudienceService:
    if AudienceService._instance is None:
        AudienceService._instance = AudienceService()
    return AudienceService._instance
