# 📱 CONTENT PUBLISHING SYSTEM GUIDE

## System Overview

Your Telegram automation system now has a **complete content publishing pipeline**:

```
RSS Feeds → Fetch Content → OpenAI Rewrite → Publish to Channel
    ↓           ↓              ↓                    ↓
5 feeds     2568+ items      Telegram-optimized   Live posts
```

---

## ✅ Current Status

- **RSS Feeds Configured**: 5 sources (Tech, Crypto, News)
- **Content Fetching**: Working ✅
- **OpenAI Rewriting**: Working ✅ ($0.0002 per article)
- **Publishing**: Ready to activate ✅
- **Target Channel**: @cryptocurrency_media (CRYPTO NEWS)
- **Auto-Publishing**: Every 60 minutes (configurable)

---

## 📸 Publishing with Photos/Media

### Method 1: Publish Text + Photo in Single Message

The current system publishes **text only**. To add photos, you have two options:

#### Option A: Manual Photo Upload (Recommended for High-Quality Content)
1. Go to **Admin Dashboard** → `/admin/paid-content`
2. Upload a photo file (JPG/PNG)
3. System stores it in `static/uploads/`
4. You can then attach to messages manually in Telegram

#### Option B: Automatic Photo Fetching from Article URLs
Enhance the publisher to extract images from articles:

```python
# In publisher_service.py (enhancement needed)
async def extract_image_from_article(self, item):
    """Extract first image from article content."""
    soup = BeautifulSoup(item['content'], 'html.parser')
    img = soup.find('img')
    if img and img.get('src'):
        return img['src']  # Return image URL
    return None
```

#### Option C: Use Stock Photo APIs
Enhance with automatic images from:
- Unsplash API (free, high-quality)
- Pexels API (free)
- Pixabay API (free)

---

## 🚀 Quick Start Publishing

### Step 1: Test Publish (No Channel Setup)
```bash
# Generate draft posts without publishing
python test_publisher.py
```
✅ Creates 1-2 draft posts, no actual publishing

### Step 2: Configure Target Channel
```bash
# Set where to publish
python set_target_channel.py cryptocurrency_media
```

### Step 3: Manual Trigger (One-Time)
```bash
# Fetch, rewrite, and publish immediately
python trigger_publish.py
```

### Step 4: Auto-Publishing (Continuous)
✅ Already running in telethon_runner!
- Runs every 60 minutes by default
- Fetches new content from 5 RSS feeds
- Rewrites with OpenAI
- Publishes to target channel

---

## 📊 What Gets Published

Each post includes:
- ✅ Title from RSS feed
- ✅ Content rewritten by OpenAI for Telegram
- ✅ Emojis and formatting for engagement
- ✅ Character limit enforced (Telegram: 4096 chars)
- ✅ Source URL preserved

**Example:**
```
🚀 **Ethereum Hits New Milestone** 📈

Major breakthrough in Ethereum's scaling...

[Rewritten with emojis, formatting, and call-to-action]

Source: CoinTelegraph
```

---

## ⚙️ Configuration

### View Configuration
```bash
python check_publisher.py
```

### Edit Settings (Admin Panel)
Go to: `http://localhost:5000/admin/settings`

Key settings:
- `target_channel`: Where to publish (e.g., @cryptocurrency_media)
- `publisher_interval_minutes`: How often to check for new content (default: 60)
- `openai_prompt_publisher`: Custom prompt for rewriting
- `openai_daily_budget`: Max spend per day ($5.00)

### Manage Content Sources
Go to: `http://localhost:5000/admin/content-sources`

- ✅ Add new RSS feeds
- ✅ Toggle feeds on/off
- ✅ Set fetch interval per feed
- ✅ Change content language

---

## 📈 Publishing Statistics

View all published posts: `/admin/published-posts`

**Displays:**
- Post title & source
- Publication date & time
- Status (published/draft/failed)
- Message ID (Telegram)
- Tokens used (OpenAI cost)

---

## 📝 Adding Custom Content Types

The system supports:
1. **RSS Feeds** ✅ (Currently enabled)
2. **Reddit Posts** (Framework ready, needs URL)
3. **Webpages** (Framework ready, needs URL)
4. **Manual Posts** (Draft creation for manual editing)

### Add Reddit as Source
```
Name: Subreddit (e.g., r/cryptocurrency)
Type: reddit
URL: https://www.reddit.com/r/cryptocurrency/
Interval: 6 hours
```

### Add Website as Source
```
Name: Tech Blog
Type: webpage
URL: https://example.com/blog
Interval: 12 hours
```

---

## 🎨 Content Customization

### Customize Rewrite Prompt
Edit in Admin → Settings:

```
<key>openai_prompt_publisher</key>

<value>
Rewrite this article as an engaging Telegram post.
Target audience: [describe your audience]
Style: [formal/casual/technical/funny]
Max length: 4000 characters
Include emojis and formatting.
Add call-to-action at the end.
</value>
```

### Set Different Prompts Per Language
Configure prompts for:
- English
- Russian (Русский)
- Spanish
- German
- etc.

---

## 🔍 Monitoring & Troubleshooting

### Check Publishing Logs
```bash
# See what's happening
tail -f worker_output.log | grep PUBLISHER
```

### Common Issues

**❌ "No content fetched"**
- Check RSS feed URLs are accessible
- Verify internet connection
- Check firewall/proxy settings

**❌ "OpenAI returned empty"**
- Check API budget not exceeded
- Verify OPENAI_API_KEY is set
- Check daily budget limit

**❌ "Failed to publish"**
- Verify target channel exists
- Check you're admin in channel
- Verify bot permissions

---

## 📱 Photo/Media Integration (TODO)

To fully automate photo publishing:

1. **Extract images from articles**
   - Modify `publisher_service.py`
   - Parse article HTML for images
   - Download and cache images

2. **Send photo + caption to Telegram**
   - Use Telethon's `send_file()` with caption
   - Example:
   ```python
   await client.send_file(channel, photo_path, caption=text)
   ```

3. **Fallback photos (if article has none)**
   - Use Unsplash API to fetch relevant image
   - Based on article keywords

---

## 🎯 Recommended RSS Feeds by Topic

### Tech & AI
- https://www.theverge.com/rss/index.xml ✅ (Added)
- https://feeds.arstechnica.com/arstechnica/index ✅ (Added)

### Crypto & Finance  
- https://cointelegraph.com/feed ✅ (Added)
- https://www.coindesk.com/feed

### General News
- https://feeds.bbci.co.uk/news/rss.xml ✅ (Added)
- https://feeds.bloomberg.com/markets/news.rss

### Lifestyle & Relationships
- https://www.cosmopolitan.com/feed
- https://www.dating-tips.world/rss

### Entrepreneurship
- https://news.ycombinator.com/rss ✅ (Added)

---

## 💾 API Endpoints

### Trigger Publishing (Manual)
```bash
curl -X POST http://localhost:5000/api/publish/trigger \
  -H "Content-Type: application/json" \
  -d '{"max_posts": 3}'
```

### Export Published Posts
```bash
curl http://localhost:5000/api/contacts/export \
  -o posts.csv
```

---

## 🔄 Next Steps

1. ✅ Test publisher: `python test_publisher.py`
2. ✅ Set target channel: `python set_target_channel.py chatting_uk` (or your channel)
3. ✅ Monitor publishing: Check `/admin/published-posts`
4. 📸 Add photo support (enhancement)
5. 🎨 Customize content prompts
6. 🌍 Add more RSS feeds

---

## Support & Debugging

### Enable Debug Logging
In telethon_runner.py:
```python
logging.basicConfig(level=logging.DEBUG)
```

### Test Individual RSS Feed
```python
from app.services.content_fetcher import ContentFetcher
fetcher = ContentFetcher()
items = fetcher.fetch_rss("https://...")
```

### Test OpenAI Rewrite
```bash
python test_publisher.py
```

---

## Performance Notes

- **Content fetching**: Respects rate limits
- **Publishing speed**: 1 post per 10 seconds (configurable)
- **OpenAI cost**: ~$0.0002 per article (with gpt-4o-mini)
- **Daily budget**: $5.00 (configurable)
- **Frequency**: Every 60 minutes (configurable)

At current settings:
- ~1-2 posts per hour
- ~5-10 posts per day (assuming new content)
- ~$0.01/day in OpenAI costs

---

**System Ready! 🚀 Publishing starts automatically in 60 minutes.**
