import logging
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from app.models import ContentSource, PublishedPost

logger = logging.getLogger(__name__)


class ContentFetcher:
    """Fetch content from RSS, Reddit, and webpages."""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def fetch_rss(self, url):
        """Fetch content from RSS feed."""
        try:
            feed = feedparser.parse(url)
            items = []
            for entry in feed.entries[:10]:  # Limit to 10 recent entries
                items.append({
                    'title': entry.get('title', 'Untitled'),
                    'content': entry.get('summary', entry.get('description', '')),
                    'url': entry.get('link', ''),
                    'published': entry.get('published_parsed', None)
                })
            logger.info(f'Fetched {len(items)} items from RSS: {url}')
            return items
        except Exception as e:
            logger.error(f'Failed to fetch RSS from {url}: {e}')
            return []

    def fetch_reddit(self, url):
        """Fetch posts from Reddit (public subreddits via JSON API)."""
        try:
            # Convert URL to JSON endpoint
            if not url.endswith('.json'):
                url = url.rstrip('/') + '.json'

            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            data = response.json()

            items = []
            posts = data.get('data', {}).get('children', [])
            for post in posts[:10]:
                post_data = post.get('data', {})
                items.append({
                    'title': post_data.get('title', 'Untitled'),
                    'content': post_data.get('selftext', ''),
                    'url': f"https://reddit.com{post_data.get('permalink', '')}",
                    'published': datetime.fromtimestamp(post_data.get('created_utc', 0))
                })

            logger.info(f'Fetched {len(items)} posts from Reddit: {url}')
            return items
        except Exception as e:
            logger.error(f'Failed to fetch Reddit from {url}: {e}')
            return []

    def fetch_webpage(self, url):
        """Fetch content from a webpage."""
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Try to extract main content
            title = soup.find('h1')
            title_text = title.get_text(strip=True) if title else 'Untitled'

            # Look for main content containers
            content_tags = soup.find_all(['article', 'main', 'div'], class_=['content', 'article', 'post'])
            if content_tags:
                content_text = ' '.join([tag.get_text(strip=True, separator=' ') for tag in content_tags])
            else:
                # Fallback: get all paragraph text
                paragraphs = soup.find_all('p')
                content_text = ' '.join([p.get_text(strip=True) for p in paragraphs[:10]])

            items = [{
                'title': title_text,
                'content': content_text[:2000],  # Limit length
                'url': url,
                'published': datetime.utcnow()
            }]

            logger.info(f'Fetched webpage: {url}')
            return items
        except Exception as e:
            logger.error(f'Failed to fetch webpage {url}: {e}')
            return []

    def fetch_source(self, source: ContentSource):
        """Fetch content from a ContentSource (routes to correct method)."""
        if source.source_type == 'rss':
            return self.fetch_rss(source.url)
        elif source.source_type == 'reddit':
            return self.fetch_reddit(source.url)
        elif source.source_type == 'webpage':
            return self.fetch_webpage(source.url)
        else:
            logger.warning(f'Unknown source type: {source.source_type}')
            return []

    def is_duplicate(self, source_url):
        """Check if content from this URL has already been published."""
        existing = PublishedPost.query.filter_by(source_url=source_url).first()
        return existing is not None
