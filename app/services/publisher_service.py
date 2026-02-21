import asyncio
import logging
import os
from datetime import datetime, timedelta
from telethon import types
from app import db
from app.models import ContentSource, PublishedPost, PostMedia, AppConfig

logger = logging.getLogger(__name__)


class PublisherService:
    _instance = None

    def __init__(self, client_manager, openai_service, content_fetcher):
        self.client_manager = client_manager
        self.openai_service = openai_service
        self.content_fetcher = content_fetcher

    async def fetch_new_content(self):
        """Fetch new content from all active sources."""
        try:
            sources = ContentSource.query.filter_by(active=True).all()
            logger.info(f'[PUBLISHER FETCH] ====== FETCHING CONTENT ======')
            logger.info(f'[PUBLISHER FETCH] Found {len(sources)} active content sources')
            
            if not sources:
                logger.error('[PUBLISHER FETCH] ❌ NO ACTIVE SOURCES CONFIGURED!')
                logger.error('[PUBLISHER FETCH] Please add content sources in admin panel:')
                logger.error('[PUBLISHER FETCH]   - Go to /admin/content-sources')
                logger.error('[PUBLISHER FETCH]   - Add RSS feeds (OpenAI, CoinDesk, etc)')
                logger.error('[PUBLISHER FETCH]   - Mark them as Active')
                return []
            
            # Show all active sources
            logger.info(f'[PUBLISHER FETCH] Active sources:')
            for idx, source in enumerate(sources, 1):
                logger.info(f'  [{idx}] {source.name} ({source.source_type})')
                logger.info(f'      URL: {source.url}')
                logger.info(f'      Interval: {source.fetch_interval_hours}h')
                if source.last_fetched:
                    logger.info(f'      Last fetched: {source.last_fetched}')
                else:
                    logger.info(f'      Last fetched: NEVER')
            
            all_items = []

            for idx, source in enumerate(sources, 1):
                logger.info(f'[PUBLISHER FETCH] [{idx}/{len(sources)}] Processing: {source.name}')
                
                # Check if it's time to fetch
                if source.last_fetched:
                    next_fetch = source.last_fetched + timedelta(hours=source.fetch_interval_hours)
                    time_until_next = (next_fetch - datetime.utcnow()).total_seconds()
                    if time_until_next > 0:
                        logger.info(f'[PUBLISHER FETCH] [{idx}] ⏱️ Not due yet (in {time_until_next:.0f}s, next: {next_fetch})')
                        continue
                    else:
                        logger.info(f'[PUBLISHER FETCH] [{idx}] ✅ Due for fetching')

                logger.info(f'[PUBLISHER FETCH] [{idx}] 🔄 Fetching from: {source.url}')
                items = self.content_fetcher.fetch_source(source)
                logger.info(f'[PUBLISHER FETCH] [{idx}] ✅ Fetched {len(items) if items else 0} items')
                
                if not items:
                    logger.warning(f'[PUBLISHER FETCH] [{idx}] ⚠️ No items returned from {source.name}')
                    # Still mark as fetched even if empty
                    source.last_fetched = datetime.utcnow()
                    db.session.commit()
                    continue
                
                # Show fetched items
                logger.info(f'[PUBLISHER FETCH] [{idx}] Items found:')
                for item_idx, item in enumerate(items[:3], 1):
                    logger.info(f'      [{item_idx}] {item["title"][:50]}...')
                
                for item in items:
                    # Skip duplicates
                    if not self.content_fetcher.is_duplicate(item['url']):
                        item['source_id'] = source.id
                        item['language'] = source.language
                        all_items.append(item)
                        logger.debug(f'[PUBLISHER FETCH] Added: {item["title"][:50]}...')
                    else:
                        logger.debug(f'[PUBLISHER FETCH] Duplicate skipped: {item["url"][:60]}...')

                # Update last_fetched
                source.last_fetched = datetime.utcnow()
                db.session.commit()
                logger.info(f'[PUBLISHER FETCH] [{idx}] Updated last_fetched for {source.name}')

            logger.info(f'[PUBLISHER FETCH] ====== COMPLETE ======')
            logger.info(f'[PUBLISHER FETCH] Result: {len(all_items)} unique items ready to publish')
            return all_items
        
        except Exception as e:
            logger.error(f'[PUBLISHER FETCH] 💥 CRITICAL ERROR: {e}', exc_info=True)
            return []

    async def rewrite_content(self, item, language):
        """Use OpenAI to rewrite content for the target language."""
        try:
            logger.info(f'[PUBLISHER REWRITE] Title: {item["title"][:60]}...')
            
            system_prompt = AppConfig.get('openai_prompt_publisher',
                'Rewrite this article for a Telegram channel. Make it engaging, concise, and add relevant emojis.')
            logger.debug(f'[PUBLISHER REWRITE] System prompt: {system_prompt[:80]}...')

            user_message = f"Title: {item['title']}\n\nContent: {item['content'][:1500]}\n\nLanguage: {language}"
            logger.debug(f'[PUBLISHER REWRITE] Input: {len(user_message)} chars')

            logger.info(f'[PUBLISHER REWRITE] Calling OpenAI API...')
            result = self.openai_service.chat(
                system_prompt=system_prompt,
                user_message=user_message,
                module='publisher'
            )

            if not result:
                logger.error(f'[PUBLISHER REWRITE] ❌ OpenAI returned None')
                return None, 0
            
            if 'content' not in result:
                logger.error(f'[PUBLISHER REWRITE] ❌ OpenAI response missing "content" key: {list(result.keys())}')
                return None, 0
            
            content = result['content']
            if not content:
                logger.warning(f'[PUBLISHER REWRITE] ❌ OpenAI returned empty content')
                return None, 0
            
            tokens = result.get('total_tokens', result.get('tokens', 0))
            logger.info(f'[PUBLISHER REWRITE] ✅ Success: {len(content)} chars, {tokens} tokens')
            return content, tokens

        except Exception as e:
            logger.error(f'[PUBLISHER REWRITE] 💥 FAILED: {e}', exc_info=True)
            return None, 0

    async def _resolve_channel_entity(self, channel_identifier):
        """Resolve channel identifier (string like '@channel') to InputPeerChannel entity.
        
        Args:
            channel_identifier: Channel username or ID (e.g., '@mychannel', -100123456789)
            
        Returns:
            InputPeerChannel entity or None if resolution fails
        """
        try:
            client = await self.client_manager.get_client()
            if not client:
                logger.error('[PUBLISH] No Telegram client available for channel resolution')
                return None
            
            logger.info(f'[PUBLISH] Resolving channel entity: {channel_identifier}')
            entity = await client.get_entity(channel_identifier)
            logger.info(f'[PUBLISH] Resolved channel entity type: {type(entity).__name__}')
            return entity
        except Exception as e:
            logger.error(f'[PUBLISH] Failed to resolve channel entity {channel_identifier}: {e}')
            return None

    async def _check_channel_permissions(self, channel_entity):
        """Check if bot has required permissions to post in channel.
        
        Args:
            channel_entity: Telethon Channel entity
            
        Returns:
            True if bot can post, False otherwise
        """
        try:
            client = await self.client_manager.get_client()
            if not client:
                logger.error('[PUBLISH] No Telegram client available for permission check')
                return False
            
            # For channels, check if bot is admin
            if isinstance(channel_entity, types.Channel):
                permissions = channel_entity.default_banned_rights
                if permissions and permissions.send_messages:
                    logger.error(f'[PUBLISH] Bot cannot send messages in channel (banned)')
                    return False
                
                logger.info(f'[PUBLISH] Channel permission check passed')
                return True
            
            logger.warning(f'[PUBLISH] Entity is not a Channel: {type(channel_entity).__name__}')
            return True  # Assume it's OK for non-channels (groups, etc.)
            
        except Exception as e:
            logger.error(f'[PUBLISH] Permission check failed: {e}')
            return False

    async def publish_to_channel(self, text, channel, media_files=None):
        """Publish a message to the Telegram channel with optional media.
        
        This method MUST:
        1. Resolve channel to InputPeerChannel entity
        2. Check bot permissions
        3. Log explicitly BEFORE sending
        4. Log explicitly AFTER sending (with message ID)
        5. Return message ID on success or None on failure
        6. NO SILENT FAILURES
        """
        try:
            # Validate inputs
            if not text:
                logger.error('[PUBLISH] Cannot publish empty text')
                return None
            
            if not channel:
                logger.error('[PUBLISH] No channel specified')
                return None
            
            # === STEP 1: Resolve channel entity ===
            channel_entity = await self._resolve_channel_entity(channel)
            if not channel_entity:
                logger.error(f'[PUBLISH] ABORT: Failed to resolve channel: {channel}')
                return None
            
            # === STEP 2: Check permissions ===
            if not await self._check_channel_permissions(channel_entity):
                logger.error(f'[PUBLISH] ABORT: Bot lacks permissions in channel: {channel}')
                return None
            
            # Get client
            client = await self.client_manager.get_client()
            if not client:
                logger.error('[PUBLISH] ABORT: No Telegram client available')
                return None
            
            # === STEP 3: Prepare media if provided ===
            media_paths = []
            if media_files:
                for media_file in media_files:
                    full_path = os.path.join('app', 'static', 'uploads', media_file['file_path'])
                    if os.path.exists(full_path):
                        media_paths.append(full_path)
                    else:
                        logger.warning(f'[PUBLISH] Media file not found: {full_path}')
            
            # === STEP 4: Log publication attempt ===
            media_info = f"({len(media_paths)} media files)" if media_paths else "(text only)"
            logger.info(f'[PUBLISH] SENDING TO: {channel}')
            logger.info(f'[PUBLISH] Content: {len(text)} chars {media_info}')
            logger.debug(f'[PUBLISH] Preview: {text[:100]}...')
            
            # === STEP 5: Send message ===
            try:
                if not media_paths:
                    # Send text only
                    logger.info(f'[PUBLISH] Executing: send_message()')
                    message = await client.send_message(channel_entity, text)
                elif len(media_paths) == 1:
                    # Send with single media
                    logger.info(f'[PUBLISH] Executing: send_file() with 1 media')
                    message = await client.send_file(channel_entity, media_paths[0], caption=text)
                else:
                    # Send with multiple media (album)
                    logger.info(f'[PUBLISH] Executing: send_file() with {len(media_paths)} media (album)')
                    message = await client.send_file(channel_entity, media_paths, caption=text)
                
                # === STEP 6: Log success ===
                logger.info(f'[PUBLISH] ✅ SUCCESS: Published to {channel}')
                logger.info(f'[PUBLISH] Message ID: {message.id}')
                logger.info(f'[PUBLISH] Message date: {message.date}')
                return message.id
                
            except Exception as send_err:
                logger.error(f'[PUBLISH] ❌ SEND FAILED: {type(send_err).__name__}: {send_err}', exc_info=True)
                logger.error(f'[PUBLISH] Debug info:')
                logger.error(f'  - Channel: {channel}')
                logger.error(f'  - Entity type: {type(channel_entity).__name__}')
                logger.error(f'  - Entity ID: {getattr(channel_entity, "id", "N/A")}')
                raise  # Re-raise to be caught by outer exception handler
        
        except Exception as e:
            logger.error(f'[PUBLISH] ❌ ABORT: {type(e).__name__}: {e}', exc_info=True)
            return None

    async def run_publish_cycle(self, max_posts=3):
        """Fetch, rewrite, and publish up to max_posts pieces of content.
        
        SEPARATED STAGES:
        1. GENERATE: Fetch and rewrite content (preparation)
        2. PUBLISH: Send to channel (execution)
        3. RECORD: Save to database (tracking)
        """
        logger.info('=' * 70)
        logger.info('[PUBLISHER CYCLE] STAGE 1/3: GENERATE (fetch & rewrite)')
        logger.info('=' * 70)
        
        target_channel = AppConfig.get('target_channel', '@your_channel')
        default_language = AppConfig.get('default_language', 'en')

        # === STAGE 1: GENERATE ===
        logger.info(f'[PUBLISHER CYCLE] Fetching new content...')
        items = await self.fetch_new_content()
        
        if not items:
            logger.warning('[PUBLISHER CYCLE] ⚠️ No new content found')
            logger.warning('[PUBLISHER CYCLE] Possible causes:')
            logger.warning('[PUBLISHER CYCLE]   1. No active content sources configured')
            logger.warning('[PUBLISHER CYCLE]   2. Content sources recently fetched (fetch interval not reached)')
            logger.warning('[PUBLISHER CYCLE]   3. All content already published (duplicates)')
            logger.warning('[PUBLISHER CYCLE]   4. Content fetch failed (check RSS URLs)')
            return 0

        items = items[:max_posts]
        logger.info(f'[PUBLISHER CYCLE] Processing {len(items)} items for publication (max: {max_posts})')

        # Pre-generate all content (separate from publishing)
        generated_items = []
        for idx, item in enumerate(items, 1):
            logger.info(f'[PUBLISHER CYCLE] [{idx}/{len(items)}] Rewriting: "{item["title"][:50]}..."')
            rewritten, tokens = await self.rewrite_content(item, item.get('language', default_language))
            
            if not rewritten:
                logger.error(f'[PUBLISHER CYCLE] [{idx}/{len(items)}] ❌ SKIPPED - rewrite failed')
                continue
            
            logger.info(f'[PUBLISHER CYCLE] [{idx}/{len(items)}] ✅ Ready - {len(rewritten)} chars')
            generated_items.append({
                'source_data': item,
                'rewritten_content': rewritten,
                'tokens': tokens
            })

        if not generated_items:
            logger.error('[PUBLISHER CYCLE] 💥 No items successfully rewritten')
            return 0

        logger.info('')
        logger.info('=' * 70)
        logger.info(f'[PUBLISHER CYCLE] STAGE 2/3: PUBLISH ({len(generated_items)} items)')
        logger.info('=' * 70)
        logger.info(f'[PUBLISHER CYCLE] Publishing to: {target_channel}')
        
        # === STAGE 2: PUBLISH ===
        published_count = 0

        for idx, item_data in enumerate(generated_items, 1):
            item = item_data['source_data']
            rewritten = item_data['rewritten_content']
            tokens = item_data['tokens']
            
            logger.info(f'[PUBLISHER CYCLE] [{idx}/{len(generated_items)}] Publishing: "{item["title"][:50]}..."')
            
            # EXPLICIT PUBLISH CALL (logs happen inside publish_to_channel)
            message_id = await self.publish_to_channel(rewritten, target_channel)

            # === STAGE 3: RECORD ===
            post = PublishedPost(
                source_id=item.get('source_id'),
                source_url=item['url'],
                source_title=item['title'],
                original_content=item['content'],
                rewritten_content=rewritten,
                telegram_message_id=message_id,
                telegram_channel=target_channel,
                language=item.get('language', default_language),
                status='published' if message_id else 'failed',
                published_at=datetime.utcnow() if message_id else None,
                tokens_used=tokens
            )
            db.session.add(post)
            db.session.commit()

            if message_id:
                published_count += 1
                logger.info(f'[PUBLISHER CYCLE] [{idx}/{len(generated_items)}] ✅ SAVED - Post ID {post.id}, Message ID {message_id}')
            else:
                logger.error(f'[PUBLISHER CYCLE] [{idx}/{len(generated_items)}] ❌ FAILED - Post ID {post.id}, publish failed')

            # Delay between posts (avoid flooding)
            if idx < len(generated_items):
                logger.info(f'[PUBLISHER CYCLE] ⏱️ Delay 10s before next post...')
                await asyncio.sleep(10)

        logger.info('')
        logger.info('=' * 70)
        logger.info('[PUBLISHER CYCLE] STAGE 3/3: COMPLETE')
        logger.info('=' * 70)
        logger.info(f'[PUBLISHER CYCLE] Published: {published_count}/{len(generated_items)} items')
        logger.info(f'[PUBLISHER CYCLE] Failed: {len(generated_items) - published_count}/{len(generated_items)} items')
        logger.info(f'[PUBLISHER CYCLE] Total processed: {len(items)} from sources')
        logger.info('=' * 70)
        
        return published_count

    def _get_publish_interval(self) -> int:
        """Get publishing interval from config (in seconds)."""
        try:
            from app.models import AppConfig
            return int(AppConfig.get('publisher_interval_minutes', '60')) * 60
        except (TypeError, ValueError):
            return 3600  # Default: 1 hour

    async def publish_scheduled_posts(self) -> int:
        """Check for and publish scheduled posts that are due.
        
        IMPORTANT: No silent failures. Each step is logged explicitly.
        """
        try:
            logger.info('[PUBLISHER SCHEDULED] Checking for scheduled posts...')
            
            # Find posts that are scheduled and due for publishing
            scheduled_posts = PublishedPost.query.filter(
                PublishedPost.status == 'scheduled',
                PublishedPost.scheduled_at <= datetime.utcnow()
            ).all()
            
            if not scheduled_posts:
                logger.info('[PUBLISHER SCHEDULED] No posts due for publishing')
                return 0
            
            logger.info(f'[PUBLISHER SCHEDULED] Found {len(scheduled_posts)} posts due for publishing')
            
            published_count = 0
            for idx, post in enumerate(scheduled_posts, 1):
                try:
                    logger.info(f'[PUBLISHER SCHEDULED] [{idx}/{len(scheduled_posts)}] Publishing post ID {post.id}')
                    
                    # Get media files for this post
                    media_items = PostMedia.query.filter_by(published_post_id=post.id).all()
                    media_files = None
                    if media_items:
                        media_files = [{'file_path': media.file_path} for media in media_items]
                        logger.info(f'[PUBLISHER SCHEDULED] Post ID {post.id} has {len(media_files)} media files')
                    
                    # Publish the post (logs happen inside publish_to_channel)
                    message_id = await self.publish_to_channel(
                        text=post.rewritten_content or post.original_content,
                        channel=post.telegram_channel,
                        media_files=media_files
                    )
                    
                    if message_id:
                        # Update post status to published
                        post.status = 'published'
                        post.published_at = datetime.utcnow()
                        db.session.commit()
                        
                        published_count += 1
                        logger.info(f'[PUBLISHER SCHEDULED] [{idx}/{len(scheduled_posts)}] SUCCESS - post ID {post.id}, message ID {message_id}')
                    else:
                        # Update post status to failed
                        post.status = 'failed'
                        db.session.commit()
                        logger.error(f'[PUBLISHER SCHEDULED] [{idx}/{len(scheduled_posts)}] FAILED - post ID {post.id}, publish_to_channel returned None')
                    
                except Exception as e:
                    logger.error(f'[PUBLISHER SCHEDULED] [{idx}/{len(scheduled_posts)}] EXCEPTION - post ID {post.id}: {e}', exc_info=True)
                    post.status = 'failed'
                    db.session.commit()
            
            logger.info(f'[PUBLISHER SCHEDULED] Complete: {published_count}/{len(scheduled_posts)} published')
            return published_count
            
        except Exception as e:
            logger.error(f'[PUBLISHER SCHEDULED] CRITICAL ERROR: {e}', exc_info=True)
            return 0

    async def run_forever(self) -> None:
        """Run publishing cycles in an infinite loop."""
        logger.info('[PUBLISHER] Starting infinite publishing loop')
        cycle_count = 0
        
        while True:
            cycle_count += 1
            logger.info('')
            logger.info('╔' + '═' * 68 + '╗')
            logger.info(f'║ 📢 PUBLISHER CYCLE #{cycle_count} STARTING '.ljust(69) + '║')
            logger.info('╚' + '═' * 68 + '╝')
            
            try:
                # Check if target channel is configured
                target_channel = AppConfig.get('target_channel')
                if not target_channel:
                    logger.error('=' * 70)
                    logger.error('🚨 CRITICAL: target_channel NOT CONFIGURED!')
                    logger.error('=' * 70)
                    logger.error('[PUBLISHER] To fix this:')
                    logger.error('[PUBLISHER]   1. Go to admin panel: /admin/settings')
                    logger.error('[PUBLISHER]   2. Set "Target Telegram channel" (e.g., @mychannel or -100123456789)')
                    logger.error('[PUBLISHER]   3. Save')
                    logger.error('[PUBLISHER] Then restart the service')
                    logger.error('=' * 70)
                else:
                    logger.info(f'✅ Target channel: {target_channel}')
                    
                    # Publish scheduled posts first
                    logger.info(f'[PUBLISHER CYCLE {cycle_count}] Stage 1/2: Checking scheduled posts...')
                    scheduled_published = await self.publish_scheduled_posts()
                    logger.info(f'[PUBLISHER CYCLE {cycle_count}] └─ Result: {scheduled_published} scheduled posts published')
                    
                    # Then publish new content from sources
                    logger.info(f'[PUBLISHER CYCLE {cycle_count}] Stage 2/2: Publishing new content...')
                    published = await self.run_publish_cycle(max_posts=2)
                    logger.info(f'[PUBLISHER CYCLE {cycle_count}] └─ Result: {published} from sources published')
                    
                    logger.info('=' * 70)
                    logger.info(f'[PUBLISHER CYCLE {cycle_count}] CYCLE COMPLETE:')
                    logger.info(f'├─ From sources: {published}')
                    logger.info(f'├─ Scheduled: {scheduled_published}')
                    logger.info(f'└─ Total: {published + scheduled_published}')
                    logger.info('=' * 70)
                
            except Exception as e:
                logger.error(f'[PUBLISHER CYCLE {cycle_count}] 💥 EXCEPTION: {e}', exc_info=True)

            interval = self._get_publish_interval()
            logger.info(f'⏱️  [WAIT] Next publishing cycle in {interval}s ({interval//60}m)...')
            await asyncio.sleep(interval)


def get_publisher_service(client_manager=None, openai_service=None, content_fetcher=None):
    """Get or create PublisherService singleton."""
    if PublisherService._instance is None and all([client_manager, openai_service, content_fetcher]):
        PublisherService._instance = PublisherService(client_manager, openai_service, content_fetcher)
    return PublisherService._instance
