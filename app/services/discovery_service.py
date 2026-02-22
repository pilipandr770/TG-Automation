"""
Discovery Service — Module 1: Channel Discovery.

Searches Telegram for channels/groups by keyword, evaluates them via
filters and OpenAI topic matching, and joins qualifying ones.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from telethon import functions, types
from telethon.errors import (
    FloodWaitError, ChannelPrivateError, 
    UsernameNotOccupiedError, UserAlreadyParticipantError,
    ChatAdminRequiredError, ChatNotModifiedError
)

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
        """Comments are REQUIRED - we only work with channels/groups where users discuss.
        
        This means:
        - Regular Chat/Group (types.Chat) - always OK
        - Channel with megagroup=True - OK (has linked discussion group)
        - Channel with gigagroup=True - OK (massive group with auto-discussion)
        - Broadcast Channel without discussions - NOT OK
        """
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
            logger.info('[SEARCH] Searching for NEW channels/groups/supergroups matching "%s"', keyword)
            
            # We search for ALL types first (channels, groups, supergroups)
            # Then filter to keep only those with comments/discussions enabled
            try:
                # SearchGlobal with broadcasts_only=False finds groups, supergroups, and channels
                request = functions.messages.SearchGlobalRequest(
                    q=keyword,
                    filter=types.InputMessagesFilterEmpty(),  # Required parameter
                    min_date=None,   # Required parameter
                    max_date=None,   # Required parameter
                    limit=50,
                    offset_rate=0,
                    offset_peer='self',
                    offset_id=0,
                    broadcasts_only=False,  # Search ALL: channels, groups, supergroups
                )
                result = await client(request)
                
                if result and hasattr(result, 'chats') and result.chats:
                    for chat in result.chats:
                        chat_id = chat.id
                        if chat_id in channels_found:
                            continue
                            
                        title = getattr(chat, 'title', 'Unknown')
                        is_channel = isinstance(chat, types.Channel)
                        is_group = isinstance(chat, types.Chat)
                        
                        # For channels: must be megagroup or gigagroup (has discussions)
                        # For groups/chats: all are OK (they support comments by definition)
                        megagroup = getattr(chat, 'megagroup', False) if is_channel else False
                        gigagroup = getattr(chat, 'gigagroup', False) if is_channel else False
                        is_supergroup = getattr(chat, 'supergroup', False) if is_channel else False
                        
                        subs = getattr(chat, 'participants_count', 0) or 0
                        
                        # Keep if:
                        # - It's a regular group/chat (types.Chat) - they support discussions
                        # - It's a Channel with megagroup=True (broadcast with discussion thread)
                        # - It's a Channel with gigagroup=True (massive group)
                        # - It's a Channel with supergroup=True (supergroup)
                        
                        keep = False
                        reason = ''
                        
                        if is_group:
                            keep = True
                            reason = 'Group (supports discussions)'
                        elif is_channel and (megagroup or gigagroup or is_supergroup):
                            keep = True
                            reason = f'Channel with discussions (megagroup={megagroup}, gigagroup={gigagroup}, supergroup={is_supergroup})'
                        
                        if keep:
                            channels_found[chat_id] = chat
                            logger.info(f'[SEARCH] ✅ Added: "{title}" ({chat_id}) - {subs} members - {reason}')
                        else:
                            chat_type = 'Channel' if is_channel else 'Group/Chat'
                            logger.debug(f'[SEARCH] ❌ Skipped: "{title}" ({chat_id}) - {chat_type} without discussions')
                
                logger.info('[SEARCH] SearchGlobal found %d qualifying channels/groups for "%s"', len(channels_found), keyword)
            except Exception as e:
                logger.warning('[SEARCH] SearchGlobal error: %s', str(e)[:150])
            
            # Method 2: Try as username directly (e.g., "photography" -> @photography)
            try:
                if not keyword.startswith('@'):
                    entity = await client.get_entity('@' + keyword)
                else:
                    entity = await client.get_entity(keyword)
                
                if isinstance(entity, types.Channel) and entity.id not in channels_found:
                    channels_found[entity.id] = entity
                    title = getattr(entity, 'title', 'Unknown')
                    subs = getattr(entity, 'participants_count', 0) or 0
                    logger.info(f'[SEARCH] Direct lookup found: "{title}" ({entity.id}) - {subs} subs')
            except Exception as e:
                logger.debug(f'[SEARCH] Direct lookup failed for "{keyword}": {type(e).__name__}')
            
            result = list(channels_found.values())
            if result:
                logger.info(f'[SEARCH] ✅ Total found for "{keyword}": {len(result)} channels')
                for ch in result[:3]:  # Log first 3 channels
                    subs = getattr(ch, 'participants_count', 0) or 0
                    logger.debug(f'  - {getattr(ch, "title", "Unknown")} ({subs} subs)')
            else:
                logger.info(f'[SEARCH] ❌ No channels found for "{keyword}"')
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
        channel_title = getattr(channel_entity, 'title', 'Unknown')
        
        result = {
            'passed': False,
            'subscriber_count': 0,
            'has_comments': False,
            'topic_score': 0.0,
            'reason': '',
        }

        # Subscriber count (from the entity's participants_count attribute)
        # Note: participants_count may be 0 for private/invited channels
        sub_count = getattr(channel_entity, 'participants_count', 0) or 0
        result['subscriber_count'] = sub_count

        min_subs = self._get_min_subscribers()
        logger.info(f'[EVAL {channel_title}] Subscribers: {sub_count} (min required: {min_subs})')
        
        # Allow channels with 0 participants_count (they may not expose it)
        # Only filter if explicitly below minimum and > 0
        if sub_count > 0 and sub_count < min_subs:
            result['reason'] = f'Too few subscribers ({sub_count} < {min_subs})'
            logger.info(f'[FILTER REJECT] {channel_title}: {result["reason"]}')
            return result
        
        if sub_count == 0:
            logger.info(f'[EVAL {channel_title}] ⚠️ Subscribers not available (participants_count=0), allowing anyway')


        # Comments check
        # We want:
        # - Regular Chat/Group (types.Chat) - always has discussions
        # - Channel with megagroup=True - has discussion thread
        # - Channel with gigagroup=True - massive group with auto-discussion
        is_chat = isinstance(channel_entity, types.Chat)
        megagroup = getattr(channel_entity, 'megagroup', False)
        gigagroup = getattr(channel_entity, 'gigagroup', False)
        
        has_comments = is_chat or megagroup or gigagroup
        result['has_comments'] = has_comments

        require_comments = self._get_require_comments()
        if is_chat:
            logger.info(f'[EVAL {channel_title}] ✅ Regular Group/Chat (always has discussions)')
        elif megagroup:
            logger.info(f'[EVAL {channel_title}] ✅ Channel with megagroup (has discussion thread)')
        elif gigagroup:
            logger.info(f'[EVAL {channel_title}] ✅ Channel with gigagroup (massive group)')
        else:
            logger.info(f'[EVAL {channel_title}] ❌ Broadcast channel without discussions')
        
        if require_comments and not has_comments:
            result['reason'] = 'Not a group/supergroup/megagroup - no discussions'
            logger.info(f'[FILTER REJECT] {channel_title}: {result["reason"]}')
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

        logger.debug(f'[EVAL {channel_title}] Checking topic relevance...')
        
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
                logger.warning(f'[EVAL {channel_title}] Could not parse topic score: {ai_result["content"]}')

        result['topic_score'] = topic_score

        min_score = self._get_min_topic_score()
        logger.debug(f'[EVAL {channel_title}] Topic score: {topic_score:.2f} (min required: {min_score})')
        
        if topic_score < min_score:
            result['reason'] = f'Topic score too low ({topic_score:.2f} < {min_score})'
            logger.info(f'[FILTER REJECT] {channel_title}: {result["reason"]}')
            return result

        result['passed'] = True
        logger.info(f'✅ [FILTER PASSED] {channel_title}: {sub_count} subs, score={topic_score:.2f}')
        result['reason'] = 'Passed all filters'
        return result

    async def join_channel(self, channel_entity) -> bool:
        """Join a channel or group using multiple strategies.

        Tries different approaches:
        1. Direct JoinChannelRequest with entity
        2. If that fails, try using username
        3. If that fails, try using channel ID
        
        Returns True on success or if already a member.
        """
        client = await self._client_manager.get_client()
        if client is None:
            logger.warning('[JOIN] No client available')
            return False

        channel_title = getattr(channel_entity, 'title', 'Unknown')
        channel_id = getattr(channel_entity, 'id', '?')
        channel_username = getattr(channel_entity, 'username', None)

        if not await self._rate_limiter.acquire('join_channel'):
            logger.warning(f'[JOIN] Rate limited for {channel_title} ({channel_id})')
            return False

        logger.info(f'[JOIN] Attempting to join: {channel_title} ({channel_id}) username={channel_username}')

        # Strategy 1: Direct join with entity
        try:
            logger.debug(f'[JOIN] Strategy 1: Direct JoinChannelRequest with entity')
            await client(functions.channels.JoinChannelRequest(
                channel=channel_entity,
            ))
            logger.info(f'✅ [JOIN SUCCESS] Joined {channel_title} ({channel_id}) - Strategy 1')
            return True
        except UserAlreadyParticipantError:
            logger.info(f'✅ [ALREADY JOINED] {channel_title} ({channel_id}) - already a member')
            return True
        except FloodWaitError as e:
            logger.warning(f'[JOIN] FloodWait on {channel_title}: {e}')
            await self._rate_limiter.handle_flood_wait(e)
            return False
        except ChannelPrivateError as e:
            logger.warning(f'[JOIN] Channel is private: {channel_title} ({channel_id})')
            return False
        except Exception as e:
            logger.warning(f'[JOIN] Strategy 1 failed: {type(e).__name__}: {str(e)[:100]}')

        # Strategy 2: Try with username if available
        if channel_username:
            try:
                logger.debug(f'[JOIN] Strategy 2: JoinChannelRequest with username @{channel_username}')
                # Resolve username to entity
                resolved = await client.get_entity(f'@{channel_username}')
                await client(functions.channels.JoinChannelRequest(
                    channel=resolved,
                ))
                logger.info(f'✅ [JOIN SUCCESS] Joined {channel_title} ({channel_id}) - Strategy 2 (username)')
                return True
            except UserAlreadyParticipantError:
                logger.info(f'✅ [ALREADY JOINED] {channel_title} ({channel_id}) - already a member')
                return True
            except Exception as e:
                logger.warning(f'[JOIN] Strategy 2 failed: {type(e).__name__}: {str(e)[:100]}')

        # Strategy 3: Try with channel ID
        try:
            logger.debug(f'[JOIN] Strategy 3: JoinChannelRequest with channel ID {channel_id}')
            await client(functions.channels.JoinChannelRequest(
                channel=channel_id,
            ))
            logger.info(f'✅ [JOIN SUCCESS] Joined {channel_title} ({channel_id}) - Strategy 3 (ID)')
            return True
        except UserAlreadyParticipantError:
            logger.info(f'✅ [ALREADY JOINED] {channel_title} ({channel_id}) - already a member')
            return True
        except Exception as e:
            logger.error(f'[JOIN] All strategies failed for {channel_title} ({channel_id}): {type(e).__name__}: {str(e)[:150]}')
            return False

    # ── smart keyword regeneration ───────────────────────────────────────

    async def check_and_regenerate_exhausted_keywords(self) -> dict:
        """Check if keywords are exhausted and auto-regenerate variants.
        
        If a keyword hasn't found new channels for N consecutive cycles,
        generate new keyword variants and add them to the search.
        
        More aggressive: regenerates after 2 cycles (not 3) for faster discovery.
        
        Returns dict with regeneration stats.
        """
        from app import db
        from app.models import SearchKeyword, DiscoveredChannel, AppConfig

        stats = {
            'keywords_checked': 0,
            'keywords_exhausted': 0,
            'variants_generated': 0,
            'cycles_threshold': 2,  # More aggressive: regenerate after 2 cycles without results
        }

        # Get business goal / target topic for context
        business_goal = AppConfig.get('business_goal', 'adult content and relationships')
        
        keywords = SearchKeyword.query.filter_by(active=True).all()
        stats['keywords_checked'] = len(keywords)
        
        logger.info(f'[REGENERATE CHECK] Checking {len(keywords)} active keywords for regeneration')

        for kw in keywords:
            # Key improvement: also check regenerated keywords (round > 0)
            # This allows multiple levels of refinement
            
            # Check if this keyword is exhausted
            # (no new channels found in last N cycles)
            if kw.cycles_without_new >= stats['cycles_threshold'] and not kw.exhausted:
                logger.info(f'[REGENERATE START] 🔄 Keyword "{kw.keyword}" exhausted!')
                logger.info(f'[REGENERATE START] ├─ Cycles without results: {kw.cycles_without_new}')
                logger.info(f'[REGENERATE START] ├─ Last used: {kw.last_used}')
                logger.info(f'[REGENERATE START] └─ Generation round: {kw.generation_round}')
                
                kw.exhausted = True
                stats['keywords_exhausted'] += 1

                # Generate 3-5 new keyword variants
                variants = await self._generate_keyword_variants(kw.keyword, business_goal)
                
                if variants:
                    logger.info(f'[REGENERATE] Generated {len(variants)} variants for "{kw.keyword}":')
                
                for variant in variants:
                    # Check if variant already exists
                    existing = SearchKeyword.query.filter_by(keyword=variant).first()
                    if existing:
                        logger.debug(f'[REGENERATE SKIP] Variant "{variant}" already exists')
                        continue

                    # Create new keyword variant with slightly higher priority
                    # so regenerated keywords get tried sooner
                    new_kw = SearchKeyword(
                        keyword=variant,
                        language=kw.language,
                        active=True,
                        priority=max(kw.priority, 50),  # Higher priority for freshly generated
                        generation_round=kw.generation_round + 1,
                        source_keyword=kw.keyword,
                    )
                    db.session.add(new_kw)
                    stats['variants_generated'] += 1
                    logger.info(f'[REGENERATE ADD] ✅ New variant: "{variant}" (priority={new_kw.priority})')

                db.session.commit()
                logger.info(f'[REGENERATE END] Completed regeneration for "{kw.keyword}" → {stats["variants_generated"]} new variants\n')

        logger.info(f'[REGENERATE SUMMARY] Checked: {stats["keywords_checked"]}, Exhausted: {stats["keywords_exhausted"]}, Generated: {stats["variants_generated"]}')
        return stats

    async def _generate_keyword_variants(self, keyword: str, business_goal: str) -> list:
        """Generate new keyword variants for a given keyword.
        
        Uses OpenAI to create related but different search terms on the same topic.
        Generates 3-5 diverse variants using different angles/approaches.
        """
        prompt = f'''Generate 5 alternative search keywords for Telegram that will help find the same communities as "{keyword}".

Target niche: {business_goal}

Requirements:
- Each keyword should be 1-4 words
- Use DIFFERENT angles and approaches (not just synonyms)
- Include both English AND Russian variants
- Focus on finding discussion groups, not just broadcast channels
- Try different phrasings: topic + "chat", "group", "community", "discussion"

Example transformation for "adult dating":
Original: adult dating
Variants: dating singles chat, hookup group, adult relationships, singles community, mature discussion

Now generate 5 variants for "{keyword}":
Reply with ONLY keywords, one per line, no numbering'''

        result = self._openai.chat(
            system_prompt='You are a Telegram search keyword expert. Generate practical, searchable keywords.',
            user_message=prompt,
            module='discovery',
        )

        if not result.get('content'):
            logger.warning(f'[GENERATE VARIANTS] No response from OpenAI for "{keyword}"')
            return []

        # Parse the response
        variants = []
        for line in result['content'].strip().split('\n'):
            variant = line.strip().lower()
            # Basic validation: 3+ characters, not a duplicate of original
            if variant and len(variant) > 3 and variant != keyword.lower():
                variants.append(variant)
                logger.debug(f'[GENERATE VARIANTS] Parsed: "{variant}"')

        logger.info(f'[GENERATE VARIANTS] Generated {len(variants)} variants for "{keyword}": {variants}')
        return variants[:5]  # Return at most 5

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
                    # Small delay to ensure API is ready
                    await asyncio.sleep(0.5)
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

        # ══════════════════════════════════════════════════════════════════
        # DIAGNOSTIC: Show what was actually saved to DB
        # ══════════════════════════════════════════════════════════════════
        try:
            db.session.commit()
            
            # Count channels in various states
            total_channels = DiscoveredChannel.query.count()
            joined_channels = DiscoveredChannel.query.filter_by(is_joined=True).count()
            not_joined = DiscoveredChannel.query.filter_by(is_joined=False).count()
            
            logger.info('')
            logger.info('🔍 [DIAGNOSTIC] Discovery Cycle DB State:')
            logger.info(f'  Total channels in DB: {total_channels}')
            logger.info(f'  ✅ Joined channels: {joined_channels}')
            logger.info(f'  ❌ Not joined: {not_joined}')
            
            if joined_channels > 0:
                joined_list = DiscoveredChannel.query.filter_by(is_joined=True).all()
                logger.info(f'  Recently joined channels:')
                for ch in joined_list[-5:]:
                    logger.info(f'    - {ch.title} (ID: {ch.telegram_id}, timestamp: {ch.join_date})')
            
        except Exception as diag_error:
            logger.error(f'[DIAGNOSTIC ERROR] {diag_error}')
            db.session.rollback()

        # Check and regenerate exhausted keywords
        logger.info('=' * 70)
        logger.info('[REGENERATE] Checking if keywords need regeneration...')
        logger.info('=' * 70)
        regen_stats = await self.check_and_regenerate_exhausted_keywords()
        stats['keywords_regenerated'] = regen_stats['variants_generated']
        
        if regen_stats['keywords_exhausted'] > 0 or regen_stats['variants_generated'] > 0:
            logger.info('=' * 70)
            logger.info(f'[REGENERATE SUMMARY] 🔄 Keyword Regeneration Results:')
            logger.info(f'├─ Keywords checked: {regen_stats["keywords_checked"]}')
            logger.info(f'├─ Keywords exhausted: {regen_stats["keywords_exhausted"]}')
            logger.info(f'├─ New variants generated: {regen_stats["variants_generated"]}')
            logger.info(f'└─ Exhaustion threshold: {regen_stats["cycles_threshold"]} cycles')
            logger.info('=' * 70)

        # Print final cycle summary
        logger.info('=' * 70)
        logger.info(f'[CYCLE SUMMARY] Discovery Cycle #{cycle_count} Complete:')
        logger.info(f'├─ Keywords processed: {stats["keywords_processed"]}')
        logger.info(f'├─ Channels found: {stats["channels_found"]}')
        logger.info(f'├─ Channels evaluated: {stats["channels_evaluated"]}')
        logger.info(f'├─ Channels passed filters: {stats["channels_passed"]}')
        logger.info(f'├─ Channels joined: {stats["channels_joined"]}')
        logger.info(f'└─ Keywords regenerated: {stats["keywords_regenerated"]}')
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
            logger.info('')
            logger.info('╔' + '═' * 68 + '╗')
            logger.info(f'║ 🔍 DISCOVERY CYCLE #{cycle_count} STARTING '.ljust(69) + '║')
            logger.info('╚' + '═' * 68 + '╝')
            
            try:
                stats = await self.run_discovery_cycle()
                
                # Show which keywords were regenerated
                from app.models import SearchKeyword
                regenerated = SearchKeyword.query.filter(
                    SearchKeyword.generation_round > 0,
                    SearchKeyword.created_at > datetime.utcnow() - timedelta(minutes=10)
                ).all()
                
                if regenerated:
                    logger.info('')
                    logger.info('🆕 Recently Regenerated Keywords (last 10 minutes):')
                    for kw in regenerated:
                        logger.info(f'   • "{kw.keyword}" (from: "{kw.source_keyword}", round: {kw.generation_round})')
                    logger.info('')
                
            except Exception as e:
                logger.error(f'[CYCLE {cycle_count}] ❌ ERROR: {e}', exc_info=True)

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
            
            interval = self._get_cycle_interval()
            logger.info(f'⏱️  [WAIT] Next discovery cycle in {interval}s ({interval//60}m)...')
            await asyncio.sleep(interval)


# ── Singleton accessor ───────────────────────────────────────────────────

def get_discovery_service() -> DiscoveryService:
    if DiscoveryService._instance is None:
        DiscoveryService._instance = DiscoveryService()
    return DiscoveryService._instance
