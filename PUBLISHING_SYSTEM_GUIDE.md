# Publishing System: Media Support & Scheduling Guide

## Overview

The publishing system has been enhanced to support:
1. **Manual Post Creation**: Admins can create posts directly from the admin panel
2. **Media File Uploads**: Support for photos and videos in posts
3. **Scheduled Publishing**: Posts can be scheduled for future publication
4. **Automatic Publishing**: The system checks for scheduled posts and publishes them at the scheduled time

## Architecture Changes

### Database Models

#### PostMedia Model
Stores metadata for media files attached to published posts:
- `id`: Primary key
- `published_post_id`: Foreign key to PublishedPost
- `media_type`: 'photo', 'video', or 'animation'
- `file_path`: Relative path to file in `app/static/uploads/`
- `file_size`: Size in bytes
- `caption`: Optional caption for individual media
- `order`: Display order in media album
- `created_at`: Timestamp

### Service Enhancements

#### Publisher Service (`app/services/publisher_service.py`)

**New Method: `publish_scheduled_posts()`**
- Checks database for posts with `status='scheduled'` and `scheduled_at <= now`
- Retrieves associated media files
- Publishes posts to Telegram channel
- Updates status to 'published' and sets `published_at` timestamp
- Handles errors gracefully, marking failed posts with `status='failed'`

**Updated Method: `run_forever()`**
- Now calls `publish_scheduled_posts()` before checking for new content from sources
- Logs count of both scheduled and source-based published posts

**Updated Method: `publish_to_channel()`**
- Accepts optional `media_files` parameter (list of dicts with 'file_path' key)
- Supports single media, media albums, text-only, and hybrid posts
- Uses `client.send_file()` for media publishing via Telethon

### Admin Routes

#### POST Handler for `/admin/published-posts`

Accepts form data:
- `title` (required): Post title
- `content` (required): Post content (Markdown supported)
- `channel`: Target Telegram channel
- `language`: Post language (for metadata)
- `media_files` (optional): Multiple file uploads (images/videos)
- `scheduled_at` (optional): Datetime for scheduled publishing

**Behavior:**
1. Creates new `PublishedPost` record with:
   - `source_type=NULL` (indicates manual creation)
   - `status='scheduled'` if `scheduled_at` provided, else `status='published'`
   - `published_at=now` if publishing immediately, else `None`
2. For each uploaded media file:
   - Saves to `app/static/uploads/post_{id}_{token}.{ext}`
   - Creates `PostMedia` record with metadata
3. Redirects with success flash message

### Admin Template

#### Published Posts Form (Modal)

Access via "Create Post" button on `/admin/published-posts` page.

**Form Fields:**
- Title input
- Content textarea (supports Markdown)
- Target Channel input (pre-filled with configured channel)
- Language select dropdown
- Media upload (multiple files, accepts images/videos)
- Scheduled At datetime picker (optional)

**Validation:**
- Title and content are required
- At least one file must be selected if publishing with media
- Datetime must be in the future for scheduled posts

## Installation & Setup

### 1. Database Migration

The `PostMedia` table is automatically created by the migration script:

```bash
python scripts/migrate_add_post_media.py
```

This script:
- Creates `post_media` table with proper schema
- Creates index on `published_post_id` for efficient queries
- Handles if table already exists

### 2. Media Directory Setup

Ensure the media upload directory exists:

```bash
mkdir -p app/static/uploads
chmod 755 app/static/uploads
```

### 3. Configuration

No additional configuration needed. The system uses:
- Existing `target_channel` AppConfig setting
- Existing `publisher_interval_minutes` setting (how often to check for scheduled posts)

## Usage Guide

### Creating an Immediate Post

1. Go to Admin → Published Posts
2. Click "Create Post" button
3. Fill in title and content
4. (Optional) Upload photos/videos
5. Leave "Schedule Posting" empty
6. Click "Create Post"
7. Post publishes immediately to Telegram channel

### Creating a Scheduled Post

1. Go to Admin → Published Posts
2. Click "Create Post" button
3. Fill in title and content
4. (Optional) Upload photos/videos
5. Set "Schedule Posting" to desired date/time
6. Click "Create Post"
7. Post is saved with `status='scheduled'`
8. At the scheduled time, the background publisher will automatically publish it

### Publishing Media Albums

- Upload multiple images/videos in one post
- They will be sent as an album to Telegram
- Captions are supported per media item (if provided)

## Technical Flow

### Immediate Publishing

```
Admin Form POST → Route Handler → Create PublishedPost(status='published')
  → Create PostMedia records → Call publish_to_channel()
  → Telethon sends to channel → Return success
```

### Scheduled Publishing

```
Background Scheduler (every publisher_interval_minutes minutes)
  → Check for posts with status='scheduled' AND scheduled_at <= now
  → For each post: Build media list → Call publish_to_channel()
  → Update status to 'published' and set published_at
  → Log success/failure
```

## Media Format Support

**Photos:**
- Format: JPG, PNG, WebP, BMP, GIF
- Size: Up to Telegram's limits (typically 5000x5000px)

**Videos:**
- Format: MP4, AVI, MOV, WebM
- Size: Up to 2GB per Telegram limits
- Duration: No limit, but consider Telegram's streaming capabilities

**Special:**
- GIFs are supported as animations
- Videos with audio are fully supported

## Error Handling

### File Upload Errors
- Invalid file type: Rejected at input level
- File too large: Handled by Flask upload limits
- Missing file: Logged and skipped

### Publishing Errors
- Channel not accessible: Logged, post marked as 'failed'
- Media not found after upload: Falls back to text-only
- Network errors: Logged, retry on next cycle

### Scheduled Post Errors
- Invalid scheduled_at: Form validation prevents this
- Publication fails: Status set to 'failed', can manually retry
- Media missing after scheduling: Text-only fallback

## Monitoring & Debugging

### View Scheduled Posts

```python
from app import db
from app.models import PublishedPost
from datetime import datetime

# List all scheduled posts
pending = PublishedPost.query.filter(
    PublishedPost.status == 'scheduled',
    PublishedPost.scheduled_at <= datetime.utcnow()
).all()

for post in pending:
    print(f"Post {post.id}: {post.source_title} → {post.telegram_channel}")
```

### View Publication Logs

Check application logs for messages like:
```
[PUBLISHER] Published scheduled post 5 to @my_channel
[PUBLISHER CYCLE 42] Complete: published 0 from sources, 1 scheduled posts
```

### Re-publish Failed Posts

```python
from app import db
from app.models import PublishedPost

# Find failed posts
failed = PublishedPost.query.filter_by(status='failed').all()

# Reset to 'published' manually, or change to 'scheduled' to retry
for post in failed:
    post.status = 'scheduled'
    post.scheduled_at = datetime.utcnow()  # Publish immediately
    
db.session.commit()
```

## FAQ

### Q: Can I edit a post after creating it?
A: Not yet through the admin interface. You can directly edit the database or delete and recreate.

### Q: What happens if I upload a file and the network fails?
A: The file is saved, but publishing fails. You can click publish again or wait for the scheduler to retry.

### Q: Can I schedule posts multiple days in advance?
A: Yes, any future datetime is supported. Posts will wait until the scheduled time arrives.

### Q: What if the server is offline when a post should publish?
A: It will publish when the server comes back online (on the next publisher cycle).

### Q: Can I use Markdown in post content?
A: Yes, Markdown is fully supported for formatting in the content field.

## Performance Considerations

- **Scheduler checks**: Every `publisher_interval_minutes` (default: 60 minutes)
- **File uploads**: Limited by Flask's `MAX_CONTENT_LENGTH` (default: 50MB)
- **Media album**: Up to ~10 items per Telegram limits
- **Database queries**: Indexed on `published_post_id` for efficient lookups

## Future Enhancements

Possible improvements:
1. Recurring/recurring scheduled posts
2. POST editing UI
3. Bulk scheduling from CSV/spreadsheet
4. Media cropping/resizing before upload
5. Post template library
6. Analytics dashboard for published posts
7. Rate limiting for scheduled posts (e.g., max 3 per day)
8. Telegram channel analytics integration
