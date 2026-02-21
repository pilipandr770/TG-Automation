"""
Discovery Service — Module 1: Channel Discovery.

Searches Telegram for channels/groups by keyword, evaluates them via
filters and OpenAI topic matching, and joins qualifying ones.
"""

import asyncio
import logging
from datetime import datetime

from telethon import functions, types
from telethon.errors import FloodWaitError, ChannelPrivateError

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Discovers and joins Telegram channels/groups based on search keywords."""

    _instance = None

    def __init__(self):
        from app.services.telegram_client import get_telegram_client_manager
        from app.services.rate_limiter import get_rate_limiter
        from app.services.openai_service import get_openai_service

        self._client_manager = get_telegram_client_manager()
        self._rate_limiter = get_rate_limiter()
        self._openai = get_openai_service()

    # ── helpers ───────────────────────────────────────────────────────────

    def _get_min_subscribers(self) -> int:
        try:
            from app.models import AppConfig
            return int(AppConfig.get('discovery_min_subscribers', '50'))
        except (TypeError, ValueError):
            return 50

    def _get_require_comments(self) -> bool:
        """Comments are REQUIRED - we only work with channels where users discuss."""
        return True

    def _get_topic_prompt(self) -> str:
        from app.models import AppConfig
        return AppConfig.get(
            'discovery_topic_prompt',
            'You are a channel evaluator. Given a channel title and description, '
            'rate from 0.0 to 1.0 how relevant it is to our target topic. '
            'Reply with ONLY a number between 0.0 and 1.0.',
        )

    def _get_topic_context(self) -> str:
        from app.models import AppConfig
        return AppConfig.get('discovery_topic_context', '')

    def _get_min_topic_score(self) -> float:
        try:
            from app.models import AppConfig
            return float(AppConfig.get('discovery_min_topic_score', '0.3'))
        except (TypeError, ValueError):
            return 0.3

    def _get_cycle_interval(self) -> int:
        """Seconds between discovery cycles."""
        try:
            from app.models import AppConfig
            return int(AppConfig.get('discovery_interval_seconds', '300'))
        except (TypeError, ValueError):
            return 300  # 5 minutes - fast for testing/local use

    # ── core methods ─────────────────────────────────────────────────────

    async def search_channels(self, keyword: str) -> list:
        """Search for NEW channels by keyword using Telegram SearchGlobal API.
        
        Uses global search to find channels across all of Telegram.
        Returns up to 50 channels matching the keyword.
        """
        client = await self._client_manager.get_client()
        if client is None:
            logger.error('No Telegram client available')
            return []

        if not await self._rate_limiter.acquire('search'):
            logger.info('Rate limited — skipping search for "%s"', keyword)
            return []

        channels_found = {}
        
        try:
            logger.info('[SEARCH] Searching for NEW channels matching "%s"', keyword)
            
            # Method 1: Use SearchGlobal to find channels by keyword
            try:
                # SearchGlobal searches across all of Telegram for channels
                request = functions.messages.SearchGlobalRequest(
                    q=keyword,
                    filter=types.InputMessagesFilterEmpty(),  # Required parameter
                    min_date=None,   # Required parameter
                    max_date=None,   # Required parameter
                    limit=50,
                    offset_rate=0,
                    offset_peer='self',
                    offset_id=0,
                    broadcasts_only=True,  # Search channels, not groups
                )
                result = await client(request)
                
                if result and hasattr(result, 'chats') and result.chats:
                    for chat in result.chats:
                        # We want channels
                        is_channel = isinstance(chat, types.Channel)
                        if is_channel and chat.id not in channels_found:
                            channels_found[chat.id] = chat
                            title = getattr(chat, 'title', 'Unknown')
                            logger.debug('[SEARCH] SearchGlobal found: %s', title)
                
                logger.info('[SEARCH] SearchGlobal found %d channels for "%s"', len(channels_found), keyword)
            except Exception as e:
                logger.debug('[SEARCH] SearchGlobal error: %s', str(e)[:100])
            
            # Method 2: Try as username directly (e.g., "photography" -> @photography)
            try:
                if not keyword.startswith('@'):
                    entity = await client.get_entity('@' + keyword)
                else:
                    entity = await client.get_entity(keyword)
                
                if isinstance(entity, types.Channel) and entity.id not in channels_found:
                    channels_found[entity.id] = entity
                    title = getattr(entity, 'title', 'Unknown')
                    logger.info('[SEARCH] Direct lookup found: %s', title)
            except Exception as e:
                logger.debug('[SEARCH] Direct lookup failed for "%s": %s', keyword, str(e)[:80])
            
            result = list(channels_found.values())
            logger.info('[SEARCH] "%s": found %d NEW channels total', keyword, len(result))
            return result
            
        except FloodWaitError as e:
            logger.warning('[SEARCH] Flood wait detected: %s', e)
            await self._rate_limiter.handle_flood_wait(e)
            return []
        except Exception as e:
            logger.error('[SEARCH] Search error for "%s": %s', keyword, str(e)[:200])
            return []

    async def evaluate_channel(self, channel_entity) -> dict:
        """Evaluate a single channel against configured filters.

        Returns a dict with keys: passed (bool), subscriber_count,
        has_comments, topic_score, reason.
        """
        result = {
            'passed': False,
            'subscriber_count': 0,
            'has_comments': False,
            'topic_score': 0.0,
            'reason': '',
        }

        # Subscriber count (from the entity's participants_count attribute)
        sub_count = getattr(channel_entity, 'participants_count', 0) or 0
        result['subscriber_count'] = sub_count

        min_subs = self._get_min_subscribers()
        if sub_count < min_subs:
            result['reason'] = f'Too few subscribers ({sub_count} < {min_subs})'
            return result

        # Comments check
        has_comments = bool(
            getattr(channel_entity, 'megagroup', False)
            or getattr(channel_entity, 'gigagroup', False)
        )
        result['has_comments'] = has_comments

        if self._get_require_comments() and not has_comments:
            result['reason'] = 'Comments/discussion not available'
            return result

        # Topic matching via OpenAI
        title = getattr(channel_entity, 'title', '') or ''
        about = getattr(channel_entity, 'about', '') or ''
        topic_context = self._get_topic_context()

        user_msg = (
            f'Target topic: {topic_context}\n\n'
            f'Channel title: {title}\n'
            f'Channel description: {about}'
        )

        ai_result = self._openai.chat(
            system_prompt=self._get_topic_prompt(),
            user_message=user_msg,
            module='discovery',
        )

        topic_score = 0.0
        if ai_result.get('content'):
            try:
                topic_score = float(ai_result['content'].strip())
                topic_score = max(0.0, min(1.0, topic_score))
            except ValueError:
                logger.warning('Could not parse topic score: %s', ai_result['content'])

        result['topic_score'] = topic_score

        min_score = self._get_min_topic_score()
        if topic_score < min_score:
            result['reason'] = f'Topic score too low ({topic_score:.2f} < {min_score})'
            return result

        result['passed'] = True
        result['reason'] = 'Passed all filters'
        return result

    async def join_channel(self, channel_entity) -> bool:
        """Join a channel or group.

        Returns True on success.
        """
        client = await self._client_manager.get_client()
        if client is None:
            logger.warning('[JOIN] No client available')
            return False

        channel_title = getattr(channel_entity, 'title', 'Unknown')
        channel_id = getattr(channel_entity, 'id', '?')

        if not await self._rate_limiter.acquire('join_channel'):
            logger.warning(f'[JOIN] Rate limited for {channel_title} ({channel_id})')
            return False

        try:
            logger.info(f'[JOIN] Attempting to join: {channel_title} ({channel_id})')
            await client(functions.channels.JoinChannelRequest(
                channel=channel_entity,
            ))
            logger.info(f'✅ [JOIN SUCCESS] Joined channel: {channel_title} ({channel_id})')
            return True
        except FloodWaitError as e:
            logger.warning(f'[JOIN] FloodWait on {channel_title}: {e}')
            await self._rate_limiter.handle_flood_wait(e)
            return False
        except ChannelPrivateError:
            logger.warning(f'[JOIN] Channel is private: {channel_title} ({channel_id})')
            return False
        except Exception as e:
            logger.error(f'[JOIN] Error joining {channel_title} ({channel_id}): {str(e)[:100]}')
            return False

    # ── smart keyword regeneration ───────────────────────────────────────

    async def check_and_regenerate_exhausted_keywords(self) -> dict:
        """Check if keywords are exhausted and auto-regenerate variants.
        
        If a keyword hasn't found new channels for N consecutive cycles,
        generate new keyword variants and add them to the search.
        
        Returns dict with regeneration stats.
        """
        from app import db
        from app.models import SearchKeyword, DiscoveredChannel, AppConfig

        stats = {
            'keywords_checked': 0,
            'keywords_exhausted': 0,
            'variants_generated': 0,
        }

        # Get business goal / target topic for context
        business_goal = AppConfig.get('business_goal', 'adult content and relationships')
        
        keywords = SearchKeyword.query.filter_by(active=True).all()
        stats['keywords_checked'] = len(keywords)

        for kw in keywords:
            # Only check non-regenerated keywords
            if kw.generation_round > 0:
                continue

            # Check if this keyword is exhausted
            # (no new channels found in last 3 cycles)
            if kw.cycles_without_new >= 3 and not kw.exhausted:
                logger.info(f'[REGENERATE] Keyword "{kw.keyword}" exhausted (3 cycles without new channels)')
                kw.exhausted = True
                stats['keywords_exhausted'] += 1

                # Generate 3 new keyword variants
                variants = await self._generate_keyword_variants(kw.keyword, business_goal)
                
                for variant in variants:
                    # Check if variant already exists
                    existing = SearchKeyword.query.filter_by(keyword=variant).first()
                    if existing:
                        continue

                    # Create new keyword variant
                    new_kw = SearchKeyword(
                        keyword=variant,
                        language=kw.language,
                        active=True,
                        priority=kw.priority - 1, 
                        generation_round=1,
                        source_keyword=kw.keyword,
                    )
                    db.session.add(new_kw)
                    stats['variants_generated'] += 1
                    logger.info(f'[REGENERATE] Generated variant: "{variant}"')

                db.session.commit()

        return stats

    async def _generate_keyword_variants(self, keyword: str, business_goal: str) -> list:
        """Generate 3 new keyword variants for a given keyword.
        
        Uses OpenAI to create related but different search terms on the same topic.
        """
        prompt = f'''Generate 3 alternative search keywords for Telegram that are related to but different from "{keyword}".
These should target the same niche: {business_goal}

Requirements:
- Each keyword should be 1-3 words
- Use different angles/approaches than the original "{keyword}"
- Focus on keywords that would find discussion groups, channels, and supergroups
- Reply with ONLY 3 keywords, one per line, no numbering

Examples if original is "adult dating":
- dating singles
- hookup chat
- adult meet'''

        result = self._openai.chat(
            system_prompt='You are a Telegram search keyword generator for niche communities.',
            user_message=prompt,
            module='discovery',
        )

        if not result.get('content'):
            return []

        # Parse the response
        variants = []
        for line in result['content'].strip().split('\n'):
            variant = line.strip().lower()
            if variant and len(variant) > 3:
                variants.append(variant)

        return variants[:3]  # Return at most 3

    async def check_discovery_limits(self) -> dict:
        """Check if we're approaching Telegram limits.
        
        Practical limits:
        - ~50,000 maximum dialogs per account
        - Each joined channel/group counts as 1 dialog
        
        Returns dict with current status and remaining capacity.
        """
        from app import db
        from app.models import DiscoveredChannel

        joined_count = DiscoveredChannel.query.filter_by(is_joined=True).count()
        practical_limit = 45000  # Leave 5k buffer before hitting API limits
        
        return {
            'joined_channels': joined_count,
            'practical_limit': practical_limit,
            'remaining_capacity': practical_limit - joined_count,
            'usage_percent': round((joined_count / practical_limit) * 100, 1),
            'approaching_limit': joined_count > practical_limit * 0.8,
        }

    # ── orchestration ────────────────────────────────────────────────────

    async def run_discovery_cycle(self) -> dict:
        """Execute one full discovery cycle over all active keywords.

        Returns a summary dict with counts.
        """
        from app import db
        from app.models import SearchKeyword, DiscoveredChannel

        logger.info('=' * 70)
        logger.info('[DISCOVERY CYCLE] Starting new cycle')
        logger.info('=' * 70)
        
        stats = {
            'keywords_processed': 0,
            'channels_found': 0,
            'channels_evaluated': 0,
            'channels_passed': 0,
            'channels_joined': 0,
            'keywords_regenerated': 0,
            'limit_status': {},
        }

        # Check discovery limits
        limit_status = await self.check_discovery_limits()
        stats['limit_status'] = limit_status
        
        if limit_status['approaching_limit']:
            logger.warning(
                f'[LIMIT] Approaching Telegram limit: {limit_status["usage_percent"]}% used '
                f'({limit_status["joined_channels"]}/{limit_status["practical_limit"]}) '
                f'remaining: {limit_status["remaining_capacity"]}'
            )

        keywords = SearchKeyword.query.filter_by(active=True).order_by(
            SearchKeyword.priority.desc()
        ).all()
        
        logger.info(f'[KEYWORDS] Processing {len(keywords)} keywords: {[kw.keyword for kw in keywords]}')

        for kw in keywords:
            logger.info(f'[SEARCH] Keyword: "{kw.keyword}"')
            entities = await self.search_channels(kw.keyword)
            stats['keywords_processed'] += 1
            logger.info(f'[SEARCH] Found {len(entities)} channels matching "{kw.keyword}"')

            # Update last_used
            kw.last_used = datetime.utcnow()
            kw.results_count = len(entities)
            # Track whether this keyword found new channels
            channels_found_this_cycle = 0

            for entity in entities:
                stats['channels_found'] += 1
                telegram_id = entity.id
                channel_title = getattr(entity, 'title', 'Unknown')

                # Skip already-known channels
                existing = DiscoveredChannel.query.filter_by(
                    telegram_id=telegram_id
                ).first()
                if existing:
                    logger.debug(f'[DISCOVERY] Channel already known: {channel_title} ({telegram_id})')
                    continue

                channels_found_this_cycle += 1
                logger.info(f'[DISCOVERY] New channel found: {channel_title} ({telegram_id})')

                # Evaluate
                stats['channels_evaluated'] += 1
                evaluation = await self.evaluate_channel(entity)
                logger.info(f'[EVALUATION] {channel_title}: passed={evaluation["passed"]}, subs={evaluation["subscriber_count"]}, score={evaluation["topic_score"]:.2f}')

                # Determine channel type
                channel_type = 'channel'
                if getattr(entity, 'megagroup', False):
                    channel_type = 'supergroup'
                elif getattr(entity, 'gigagroup', False):
                    channel_type = 'supergroup'
                elif isinstance(entity, types.Chat):
                    channel_type = 'group'

                # Persist
                discovered = DiscoveredChannel(
                    telegram_id=telegram_id,
                    username=getattr(entity, 'username', None),
                    title=getattr(entity, 'title', ''),
                    description=getattr(entity, 'about', ''),
                    channel_type=channel_type,
                    subscriber_count=evaluation['subscriber_count'],
                    has_comments=evaluation['has_comments'],
                    topic_match_score=evaluation['topic_score'],
                    search_keyword_id=kw.id,
                    status='found',
                )

                if evaluation['passed']:
                    stats['channels_passed'] += 1
                    logger.info(f'[JOIN ATTEMPT] {channel_title} ({telegram_id}) - passed filters')
                    joined = await self.join_channel(entity)
                    if joined:
                        discovered.is_joined = True
                        discovered.join_date = datetime.utcnow()
                        discovered.status = 'joined'
                        stats['channels_joined'] += 1
                        logger.info(f'✅ [SAVED JOINED] {channel_title} is_joined=True')
                    else:
                        logger.warning(f'❌ [JOIN FAILED] {channel_title} - join attempt failed, saving as not_joined')
                        discovered.status = 'join_failed'
                else:
                    logger.info(f'[SKIP] {channel_title} - did not pass evaluation filters')

                db.session.add(discovered)

            # Update tracking of cycles without new channels
            if channels_found_this_cycle == 0:
                kw.cycles_without_new += 1
                logger.info(f'[TRACK] "{kw.keyword}" - no new channels ({kw.cycles_without_new} cycles)')
            else:
                kw.cycles_without_new = 0
                logger.info(f'[TRACK] "{kw.keyword}" - found {channels_found_this_cycle} new channels')

            db.session.commit()

        # Check and regenerate exhausted keywords
        logger.info('[REGENERATE] Checking if keywords are exhausted...')
        regen_stats = await self.check_and_regenerate_exhausted_keywords()
        stats['keywords_regenerated'] = regen_stats['variants_generated']
        if regen_stats['keywords_exhausted'] > 0:
            logger.info(f'[REGENERATE] Exhausted {regen_stats["keywords_exhausted"]} keywords, generated {regen_stats["variants_generated"]} variants')

        # Print final cycle summary
        logger.info('=' * 70)
        logger.info(f'[CYCLE SUMMARY] Found: {stats["channels_found"]}, Evaluated: {stats["channels_evaluated"]}, Passed: {stats["channels_passed"]}, Joined: {stats["channels_joined"]}')
        logger.info('=' * 70)
        
        return stats

    async def run_forever(self) -> None:
        """Run discovery cycles in an infinite loop with periodic audience scans."""
        logger.info('[START] Discovery service starting infinite loop')
        cycle_count = 0
        last_audience_scan = datetime.utcnow()
        audience_scan_interval = 600  # Scan every 10 minutes (instead of 1 hour)
        
        while True:
            cycle_count += 1
            try:
                logger.info(f'[CYCLE {cycle_count}] Starting discovery...')
                stats = await self.run_discovery_cycle()
                logger.info(f'[CYCLE {cycle_count}] Complete: {stats}')
                
                # Check if it's time to run audience scan
                now = datetime.utcnow()
                time_since_scan = (now - last_audience_scan).total_seconds()
                
                if time_since_scan >= audience_scan_interval:
                    logger.info('[AUDIENCE] Starting background audience scan (every 10 minutes)...')
                    try:
                        from app.services.audience_service import AudienceService
                        audience_service = AudienceService()
                        # Use the same client manager to avoid encryption key issues
                        audience_service._client_manager = self._client_manager
                        
                        scan_result = await audience_service.run_audience_scan()
                        logger.info(f'[AUDIENCE] Scan complete: channels={scan_result["channels_scanned"]}, messages={scan_result["messages_read"]}, contacts_saved={scan_result["saved_contacts"]}')
                        last_audience_scan = now
                    except Exception as e:
                        logger.error(f'[AUDIENCE] Scan error: {e}', exc_info=True)
                
            except Exception as e:
                logger.error(f'[CYCLE {cycle_count}] ERROR: {e}', exc_info=True)

            interval = self._get_cycle_interval()
            logger.info(f'[WAIT] Next cycle in {interval}s...')
            await asyncio.sleep(interval)


# ── Singleton accessor ───────────────────────────────────────────────────

def get_discovery_service() -> DiscoveryService:
    if DiscoveryService._instance is None:
        DiscoveryService._instance = DiscoveryService()
    return DiscoveryService._instance
