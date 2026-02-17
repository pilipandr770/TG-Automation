import asyncio
import logging
from datetime import datetime, timedelta
from app import db
from app.models import ContentSource, PublishedPost, AppConfig

logger = logging.getLogger(__name__)


class PublisherService:
    _instance = None

    def __init__(self, client_manager, openai_service, content_fetcher):
        self.client_manager = client_manager
        self.openai_service = openai_service
        self.content_fetcher = content_fetcher

    async def fetch_new_content(self):
        """Fetch new content from all active sources."""
        sources = ContentSource.query.filter_by(active=True).all()
        all_items = []

        for source in sources:
            # Check if it's time to fetch
            if source.last_fetched:
                next_fetch = source.last_fetched + timedelta(hours=source.fetch_interval_hours)
                if datetime.utcnow() < next_fetch:
                    continue

            items = self.content_fetcher.fetch_source(source)
            for item in items:
                # Skip duplicates
                if not self.content_fetcher.is_duplicate(item['url']):
                    item['source_id'] = source.id
                    item['language'] = source.language
                    all_items.append(item)

            # Update last_fetched
            source.last_fetched = datetime.utcnow()
            db.session.commit()

        logger.info(f'Fetched {len(all_items)} new items from {len(sources)} sources')
        return all_items

    async def rewrite_content(self, item, language):
        """Use OpenAI to rewrite content for the target language."""
        try:
            system_prompt = AppConfig.get('openai_prompt_publisher',
                'Rewrite this article for a Telegram channel. Make it engaging, concise, and add relevant emojis.')

            user_message = f"Title: {item['title']}\n\nContent: {item['content'][:1500]}\n\nLanguage: {language}"

            result = self.openai_service.chat(
                system_prompt=system_prompt,
                user_message=user_message,
                module='publisher'
            )

            if result and 'content' in result and result['content']:
                return result['content'], result.get('total_tokens', result.get('tokens', 0))
            else:
                logger.warning('OpenAI returned empty result')
                return None, 0

        except Exception as e:
            logger.error(f'Failed to rewrite content: {e}')
            return None, 0

    async def publish_to_channel(self, text, channel):
        """Publish a message to the Telegram channel."""
        try:
            client = await self.client_manager.get_client()
            if not client:
                logger.error('No Telegram client available')
                return None

            message = await client.send_message(channel, text)
            logger.info(f'Published post to {channel}, message ID: {message.id}')
            return message.id

        except Exception as e:
            logger.error(f'Failed to publish to channel {channel}: {e}')
            return None

    async def run_publish_cycle(self, max_posts=3):
        """Fetch, rewrite, and publish up to max_posts pieces of content."""
        target_channel = AppConfig.get('target_channel', '@your_channel')
        default_language = AppConfig.get('default_language', 'en')

        # Fetch new content
        items = await self.fetch_new_content()
        if not items:
            logger.info('No new content to publish')
            return 0

        # Limit to max_posts
        items = items[:max_posts]
        published_count = 0

        for item in items:
            # Rewrite content
            rewritten, tokens = await self.rewrite_content(item, item.get('language', default_language))
            if not rewritten:
                logger.warning(f"Skipping item {item['title']} - rewrite failed")
                continue

            # Publish to channel
            message_id = await self.publish_to_channel(rewritten, target_channel)

            # Save to database
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
                logger.info(f'Successfully published: {item["title"]}')

            # Delay between posts
            if item != items[-1]:
                await asyncio.sleep(10)

        logger.info(f'Publish cycle completed: {published_count}/{len(items)} published')
        return published_count

    def _get_publish_interval(self) -> int:
        """Get publishing interval from config (in seconds)."""
        try:
            from app.models import AppConfig
            return int(AppConfig.get('publisher_interval_minutes', '60')) * 60
        except (TypeError, ValueError):
            return 3600  # Default: 1 hour

    async def run_forever(self) -> None:
        """Run publishing cycles in an infinite loop."""
        logger.info('[PUBLISHER] Starting infinite publishing loop')
        cycle_count = 0
        
        while True:
            cycle_count += 1
            try:
                logger.info(f'[PUBLISHER CYCLE {cycle_count}] Checking for content...')
                
                # Check if target channel is configured
                target_channel = AppConfig.get('target_channel')
                if not target_channel:
                    logger.warning('[PUBLISHER] No target_channel configured - skipping publish cycle')
                else:
                    published = await self.run_publish_cycle(max_posts=2)
                    logger.info(f'[PUBLISHER CYCLE {cycle_count}] Complete: published {published} posts')
                
            except Exception as e:
                logger.error(f'[PUBLISHER CYCLE {cycle_count}] ERROR: {e}', exc_info=True)

            interval = self._get_publish_interval()
            logger.info(f'[PUBLISHER] Next cycle in {interval}s...')
            await asyncio.sleep(interval)


def get_publisher_service(client_manager=None, openai_service=None, content_fetcher=None):
    """Get or create PublisherService singleton."""
    if PublisherService._instance is None and all([client_manager, openai_service, content_fetcher]):
        PublisherService._instance = PublisherService(client_manager, openai_service, content_fetcher)
    return PublisherService._instance
