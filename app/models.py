from datetime import datetime
from flask_login import UserMixin
from app import db


# ─── Core Models ───────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AppConfig(db.Model):
    """Key-value configuration store."""
    __tablename__ = 'app_config'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get(cls, key, default=None):
        try:
            # Check if we're in an app context
            from flask import current_app
            current_app
        except RuntimeError:
            # No app context - need to create one
            from app import create_app
            app = create_app()
            with app.app_context():
                return cls.get(key, default)
        
        try:
            config = cls.query.filter_by(key=key).first()
            return config.value if config else default
        except Exception as e:
            # Handle pending rollback errors - rollback and retry
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f'Error reading config {key}: {e}, attempting rollback')
            db.session.rollback()
            try:
                config = cls.query.filter_by(key=key).first()
                return config.value if config else default
            except:
                return default

    @classmethod
    def set(cls, key, value, description=None):
        try:
            # Check if we're in an app context
            from flask import current_app
            current_app
        except RuntimeError:
            # No app context - need to create one
            from app import create_app
            app = create_app()
            with app.app_context():
                return cls.set(key, value, description)
        
        try:
            config = cls.query.filter_by(key=key).first()
            if config:
                config.value = value
                if description:
                    config.description = description
            else:
                config = cls(key=key, value=value, description=description)
                db.session.add(config)
            db.session.commit()
            return config
        except Exception as e:
            # Handle constraint violations and other errors
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f'Error setting config {key}: {e}, attempting rollback')
            db.session.rollback()
            try:
                config = cls.query.filter_by(key=key).first()
                if config:
                    config.value = value
                    if description:
                        config.description = description
                else:
                    config = cls(key=key, value=value, description=description)
                    db.session.add(config)
                db.session.commit()
                return config
            except Exception as retry_error:
                logger.error(f'Failed to set config {key} even after rollback: {retry_error}')
                db.session.rollback()
                return None


class TelegramSession(db.Model):
    """Stores Telethon StringSession for persistence on Render.com."""
    __tablename__ = 'telegram_sessions'
    id = db.Column(db.Integer, primary_key=True)
    session_name = db.Column(db.String(100), unique=True, nullable=False, default='default')
    session_string = db.Column(db.Text)
    api_id = db.Column(db.Integer)
    api_hash = db.Column(db.String(64))
    phone_number = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    last_connected = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── Module 1: Channel Discovery ──────────────────────────────────────────────

class SearchKeyword(db.Model):
    __tablename__ = 'search_keywords'
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(255), nullable=False)
    language = db.Column(db.String(10), default='en')
    active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)
    results_count = db.Column(db.Integer, default=0)
    # Tracking exhausted keywords for smart regeneration
    exhausted = db.Column(db.Boolean, default=False)
    cycles_without_new = db.Column(db.Integer, default=0)  # Tracks cycles with no new channels
    generation_round = db.Column(db.Integer, default=0)    # 0=original, 1,2,3=regenerated variants
    source_keyword = db.Column(db.String(255))              # Original keyword if this is regenerated
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DiscoveredChannel(db.Model):
    __tablename__ = 'discovered_channels'
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(255))
    title = db.Column(db.String(500))
    description = db.Column(db.Text)
    channel_type = db.Column(db.String(20))  # channel, group, supergroup
    subscriber_count = db.Column(db.Integer, default=0)
    has_comments = db.Column(db.Boolean, default=False)
    is_joined = db.Column(db.Boolean, default=False)
    join_date = db.Column(db.DateTime)
    is_blacklisted = db.Column(db.Boolean, default=False)
    blacklist_reason = db.Column(db.String(255))
    topic_match_score = db.Column(db.Float, default=0.0)
    search_keyword_id = db.Column(db.Integer, db.ForeignKey('search_keywords.id'))
    search_keyword = db.relationship('SearchKeyword', backref='channels')
    status = db.Column(db.String(20), default='found')  # found, joined, left, banned
    last_scanned_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── Module 2: Target Audience ────────────────────────────────────────────────

class AudienceCriteria(db.Model):
    __tablename__ = 'audience_criteria'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    keywords = db.Column(db.Text)  # Comma-separated keywords
    openai_prompt = db.Column(db.Text)  # Custom prompt for AI analysis
    min_confidence = db.Column(db.Float, default=0.5)  # Lowered to 0.5 to save real target_audience users
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Contact(db.Model):
    __tablename__ = 'contacts'
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    bio = db.Column(db.Text)
    language_code = db.Column(db.String(10))
    confidence_score = db.Column(db.Float, default=0.0)
    analysis_summary = db.Column(db.Text)
    source_channel_id = db.Column(db.Integer, db.ForeignKey('discovered_channels.id'))
    source_channel = db.relationship('DiscoveredChannel', backref='contacts')
    source_message_text = db.Column(db.Text)
    criteria_id = db.Column(db.Integer, db.ForeignKey('audience_criteria.id'))
    criteria = db.relationship('AudienceCriteria', backref='contacts')
    # Category: admin, competitor, bot, promoter, spam, target_audience
    category = db.Column(db.String(20), default='target_audience')
    status = db.Column(db.String(20), default='identified')  # identified, invited, responded, blocked
    invitation_sent = db.Column(db.Boolean, default=False)
    invitation_sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── Module 3: Invitation Sending ─────────────────────────────────────────────

class InvitationTemplate(db.Model):
    __tablename__ = 'invitation_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)  # Supports {first_name}, {username}
    language = db.Column(db.String(10), default='en')
    active = db.Column(db.Boolean, default=True)
    use_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InvitationLog(db.Model):
    __tablename__ = 'invitation_logs'
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    contact = db.relationship('Contact', backref='invitation_logs')
    template_id = db.Column(db.Integer, db.ForeignKey('invitation_templates.id'))
    template = db.relationship('InvitationTemplate', backref='logs')
    target_channel = db.Column(db.String(255))
    message_text = db.Column(db.Text)
    status = db.Column(db.String(20), default='sent')  # sent, delivered, read, failed, blocked
    error_message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('contact_id', name='uq_one_invitation_per_contact'),
    )


# ─── Module 4: Content Publishing ─────────────────────────────────────────────

class ContentSource(db.Model):
    __tablename__ = 'content_sources'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    source_type = db.Column(db.String(50), default='rss')  # rss, reddit, webpage
    language = db.Column(db.String(10), default='en')
    active = db.Column(db.Boolean, default=True)
    fetch_interval_hours = db.Column(db.Integer, default=6)
    last_fetched = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PublishedPost(db.Model):
    __tablename__ = 'published_posts'
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('content_sources.id'))
    source = db.relationship('ContentSource', backref='posts')
    source_url = db.Column(db.String(500))
    source_title = db.Column(db.String(500))
    original_content = db.Column(db.Text)
    rewritten_content = db.Column(db.Text)
    telegram_message_id = db.Column(db.BigInteger)
    telegram_channel = db.Column(db.String(255))
    language = db.Column(db.String(10), default='en')
    status = db.Column(db.String(20), default='draft')  # draft, scheduled, published, failed
    scheduled_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    tokens_used = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PostMedia(db.Model):
    """Store images/videos for posts"""
    __tablename__ = 'post_media'
    id = db.Column(db.Integer, primary_key=True)
    published_post_id = db.Column(db.Integer, db.ForeignKey('published_posts.id'))
    published_post = db.relationship('PublishedPost', backref='media_files')
    media_type = db.Column(db.String(20), default='photo')  # photo, video, animation
    file_path = db.Column(db.String(500), nullable=False)  # relative path
    file_size = db.Column(db.Integer)  # bytes
    caption = db.Column(db.String(255))  # caption for media
    order = db.Column(db.Integer, default=0)  # Order in album
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── Module 5: Conversations & Payments ───────────────────────────────────────

class PaidContent(db.Model):
    __tablename__ = 'paid_content'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)  # Optional paid-content specific instructions for AI
    content_type = db.Column(db.String(50))  # photo, video, recipe, document, bundle
    file_path = db.Column(db.String(500))
    thumbnail_path = db.Column(db.String(500))
    price_stars = db.Column(db.Integer, nullable=False, default=1)
    category = db.Column(db.String(100))
    language = db.Column(db.String(10), default='en')
    active = db.Column(db.Boolean, default=True)
    sales_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Conversation(db.Model):
    __tablename__ = 'conversations'
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.BigInteger, nullable=False, index=True, unique=True)
    username = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    is_subscriber = db.Column(db.Boolean, default=False)
    total_messages = db.Column(db.Integer, default=0)
    total_stars_paid = db.Column(db.Integer, default=0)
    language = db.Column(db.String(10))
    status = db.Column(db.String(20), default='active')  # active, paused, blocked
    last_message_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ConversationMessage(db.Model):
    __tablename__ = 'conversation_messages'
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)
    conversation = db.relationship('Conversation', backref='messages')
    role = db.Column(db.String(20))  # user, assistant
    content = db.Column(db.Text)
    telegram_msg_id = db.Column(db.BigInteger)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StarTransaction(db.Model):
    __tablename__ = 'star_transactions'
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.BigInteger, nullable=False)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'))
    conversation = db.relationship('Conversation', backref='transactions')
    paid_content_id = db.Column(db.Integer, db.ForeignKey('paid_content.id'))
    paid_content = db.relationship('PaidContent', backref='transactions')
    amount_stars = db.Column(db.Integer, nullable=False)
    telegram_payment_id = db.Column(db.String(255))
    status = db.Column(db.String(20), default='completed')  # completed, refunded, failed
    content_delivered = db.Column(db.Boolean, default=False)
    delivered_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── System / Logging ─────────────────────────────────────────────────────────

class TaskLog(db.Model):
    __tablename__ = 'task_logs'
    id = db.Column(db.Integer, primary_key=True)
    task_type = db.Column(db.String(50), nullable=False)
    task_id = db.Column(db.String(100))
    status = db.Column(db.String(20), default='started')  # started, running, completed, failed
    details = db.Column(db.Text)
    error_message = db.Column(db.Text)
    items_processed = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)


class OpenAIUsageLog(db.Model):
    __tablename__ = 'openai_usage_logs'
    id = db.Column(db.Integer, primary_key=True)
    module = db.Column(db.String(50))
    operation = db.Column(db.String(100))
    model = db.Column(db.String(50))
    prompt_tokens = db.Column(db.Integer, default=0)
    completion_tokens = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)
    cost_estimate = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
