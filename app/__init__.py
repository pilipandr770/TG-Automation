import os
import click
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.security import generate_password_hash
from sqlalchemy import text

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
csrf = CSRFProtect()

logger = logging.getLogger(__name__)


def _seed_fresh_database_defaults(app):
    """Populate a fresh operational database with a minimal working baseline."""
    from app.models import (
        AppConfig,
        AudienceCriteria,
        ContentSource,
        InvitationTemplate,
        SearchKeyword,
    )

    target_channel = (
        app.config.get('TELEGRAM_TARGET_CHANNEL')
        or os.getenv('TELEGRAM_TARGET_CHANNEL')
        or '@your_channel'
    )

    config_defaults = {
        'business_goal': 'Find active crypto and web3 communities, identify engaged members, and invite them to the target Telegram channel.',
        'discovery_topic_context': 'crypto, web3, trading, blockchain, defi, meme coins, airdrops, ton',
        'target_channel': target_channel,
        'discovery_enabled': 'true',
        'discovery_interval_minutes': '30',
        'discovery_interval_seconds': '1800',
        'min_subscribers_filter': '150',
        'discovery_min_subscribers': '150',
        'discovery_require_comments': 'true',
        'audience_scan_interval_minutes': '30',
        'audience_scan_interval': '1800',
        'audience_message_limit': '150',
        'audience_analysis_cap_per_channel': '30',
        'invitation_batch_size': '15',
        'daily_invitation_limit': '80',
        'openai_enabled': 'true',
        'discovery_max_active_keywords': '40',
        'discovery_keyword_cooldown_minutes': '360',
        'discovery_channel_retry_base_minutes': '60',
        'discovery_channel_retry_max_minutes': '1440',
        'discovery_low_quality_keyword_threshold': '0.35',
    }

    keywords = [
        ('crypto', 'en', 100),
        ('web3', 'en', 95),
        ('blockchain', 'en', 90),
        ('defi', 'en', 85),
        ('ton', 'en', 80),
        ('airdrop', 'en', 75),
        ('meme coin', 'en', 70),
        ('trading chat', 'en', 65),
        ('crypto signals', 'en', 60),
        ('altcoins', 'en', 55),
        ('крипта', 'uk', 100),
        ('криптовалюта', 'uk', 95),
        ('блокчейн', 'uk', 90),
        ('трейдинг', 'uk', 85),
        ('дефі', 'uk', 80),
        ('ейрдроп', 'uk', 75),
        ('тон', 'uk', 70),
        ('мемкоін', 'uk', 65),
        ('крипто чат', 'uk', 60),
        ('web3 чат', 'uk', 55),
    ]

    criteria = AudienceCriteria(
        name='Crypto Community Members',
        keywords='crypto,web3,blockchain,trading,defi,airdrop,ton,крипта,трейдинг,криптовалюта,дефі',
        openai_prompt=(
            'Analyze the Telegram user message and profile in the context of crypto and web3 communities. '
            'Return strict JSON with keys category, confidence, summary. '
            'Use category=target_audience only for real engaged people interested in crypto, trading, blockchain, TON, DeFi, airdrops, or adjacent topics. '
            'Use category=spam, promoter, bot, admin, or competitor when appropriate.'
        ),
        min_confidence=0.55,
        active=True,
    )

    template = InvitationTemplate(
        name='Crypto Invite UA',
        body=(
            'Привіт, {first_name}! Бачив твою активність у {channel}. '
            'У нас збирається Telegram-канал про крипту, web3 та робочі ідеї по ринку. '
            'Якщо цікаво, зазирни: {channel}'
        ),
        language='uk',
        active=True,
    )

    sources = [
        ContentSource(
            name='Cointelegraph',
            url='https://cointelegraph.com/rss',
            source_type='rss',
            language='en',
            active=True,
            fetch_interval_hours=6,
        ),
        ContentSource(
            name='CoinDesk',
            url='https://www.coindesk.com/arc/outboundfeeds/rss/',
            source_type='rss',
            language='en',
            active=True,
            fetch_interval_hours=6,
        ),
        ContentSource(
            name='Bits Media',
            url='https://bits.media/rss/',
            source_type='rss',
            language='uk',
            active=True,
            fetch_interval_hours=6,
        ),
    ]

    for key, value in config_defaults.items():
        if not AppConfig.query.filter_by(key=key).first():
            db.session.add(AppConfig(key=key, value=value))

    for keyword, language, priority in keywords:
        exists = SearchKeyword.query.filter_by(keyword=keyword, language=language).first()
        if not exists:
            db.session.add(SearchKeyword(keyword=keyword, language=language, priority=priority, active=True))

    if not AudienceCriteria.query.first():
        db.session.add(criteria)

    if not InvitationTemplate.query.first():
        db.session.add(template)

    if ContentSource.query.count() == 0:
        db.session.add_all(sources)

    db.session.commit()
    logger.warning('Seeded fresh database defaults for target channel %s', target_channel)


def _bootstrap_fresh_database(app):
    """Seed baseline data only when the operational tables are empty."""
    from app.models import (
        AppConfig,
        AudienceCriteria,
        Contact,
        ContentSource,
        DiscoveredChannel,
        InvitationTemplate,
        SearchKeyword,
    )

    should_seed = False
    database_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '') or ''
    lock_id = 735018

    try:
        if database_uri.startswith('postgresql'):
            db.session.execute(text('SELECT pg_advisory_lock(:lock_id)'), {'lock_id': lock_id})

        should_seed = all([
            AppConfig.query.count() == 0,
            SearchKeyword.query.count() == 0,
            DiscoveredChannel.query.count() == 0,
            Contact.query.count() == 0,
            AudienceCriteria.query.count() == 0,
            InvitationTemplate.query.count() == 0,
            ContentSource.query.count() == 0,
        ])

        if should_seed:
            _seed_fresh_database_defaults(app)
    except Exception as e:
        db.session.rollback()
        logger.warning('Fresh-database bootstrap skipped: %s', e)
    finally:
        if database_uri.startswith('postgresql'):
            try:
                db.session.execute(text('SELECT pg_advisory_unlock(:lock_id)'), {'lock_id': lock_id})
                db.session.commit()
            except Exception:
                db.session.rollback()


def _run_column_migrations(connection):
    """Apply incremental ADD COLUMN migrations safely (idempotent).

    Each statement is executed and committed individually so that a lock
    conflict on one table never deadlocks an unrelated ALTER TABLE.
    ``connection`` is accepted for API compatibility but is not used —
    each migration opens its own autocommit connection instead.
    """
    from sqlalchemy import create_engine
    migrations = [
        # contacts.access_hash — needed to send DMs after entity cache is cleared
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS access_hash BIGINT",
        "ALTER TABLE search_keywords ADD COLUMN IF NOT EXISTS next_eligible_at TIMESTAMP",
        "ALTER TABLE search_keywords ADD COLUMN IF NOT EXISTS quality_score DOUBLE PRECISION DEFAULT 1.0",
        "ALTER TABLE discovered_channels ADD COLUMN IF NOT EXISTS last_scanned_message_id BIGINT",
        "ALTER TABLE discovered_channels ADD COLUMN IF NOT EXISTS last_evaluated_at TIMESTAMP",
        "ALTER TABLE discovered_channels ADD COLUMN IF NOT EXISTS last_join_attempt_at TIMESTAMP",
        "ALTER TABLE discovered_channels ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMP",
        "ALTER TABLE discovered_channels ADD COLUMN IF NOT EXISTS evaluation_fail_count INTEGER DEFAULT 0",
        "ALTER TABLE discovered_channels ADD COLUMN IF NOT EXISTS join_fail_count INTEGER DEFAULT 0",
        "ALTER TABLE discovered_channels ADD COLUMN IF NOT EXISTS retry_reason VARCHAR(255)",
    ]
    # Run each ALTER TABLE in its own isolated transaction so lock contention
    # on one table cannot deadlock unrelated concurrent queries.
    for sql in migrations:
        try:
            with db.engine.begin() as conn:
                conn.execute(text(sql))
        except Exception as e:
            # Ignore duplicate-column errors (column already exists)
            if 'duplicate column' not in str(e).lower() and 'already exists' not in str(e).lower():
                logger.warning(f'Migration skipped: {sql!r} — {e}')


def _ensure_required_config_keys(app):
    """Insert any config keys that must exist but may be missing in older deployments.

    Only inserts if the key is absent — never overwrites values the admin may
    have changed.  Add new keys here when they are introduced post-initial-seed.
    """
    must_have = {
        'discovery_require_comments': 'true',
        'daily_invitation_limit': '80',
        'invitation_min_delay_seconds': '60',
        'invitation_max_delay_seconds': '180',
        # OpenAI defaults — seeded once, admin can override via /admin/instructions
        'openai_model': 'gpt-4o-mini',
        'openai_daily_budget': '5.0',
        'openai_prompt_conversation': (
            'Ти — дружній AI-асистент Telegram-каналу про авто з Європи та аукціони. '
            'Відповідай ТІЛЬКИ українською мовою. '
            'Будь корисним, доброзичливим і лаконічним. '
            'Якщо питання стосується авто, розмитнення або аукціонів — давай детальну відповідь. '
            'Ненав\'язливо пропонуй підписатися на канал для актуальних пропозицій.'
        ),
        'openai_prompt_channel_comments': (
            'Ти — експерт з авто з Європи та аукціонів. '
            'Відповідай ТІЛЬКИ українською мовою на коментарі у каналі. '
            'Давай конкретні, корисні відповіді. Будь коротким і по суті.'
        ),
    }
    try:
        from app.models import AppConfig
        inserted = []
        for key, default in must_have.items():
            if not AppConfig.query.filter_by(key=key).first():
                db.session.add(AppConfig(key=key, value=default))
                inserted.append(key)
        if inserted:
            db.session.commit()
            logger.info('Inserted missing config keys: %s', inserted)
    except Exception as e:
        db.session.rollback()
        logger.warning('_ensure_required_config_keys failed: %s', e)


def create_app(config_name=None):
    app = Flask(__name__)

    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    from config import config as config_dict
    app.config.from_object(config_dict.get(config_name, config_dict['default']))

    if hasattr(config_dict.get(config_name), 'init_app'):
        config_dict[config_name].init_app(app)

    # Ensure upload folder exists
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'app/static/uploads'), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Ensure csrf_token is available in all templates
    # Flask-WTF should provide this via context processor automatically,
    # but we add it explicitly as a fallback
    from flask_wtf.csrf import generate_csrf
    
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=generate_csrf)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return db.session.get(User, int(user_id))

    # Register blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.api_routes import api_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')

    # CSRF Error Handler
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        """Handle CSRF token errors."""
        from flask import request
        logger.error(f'CSRF Error: {e.description}')
        logger.error(f'Request path: {request.path}')
        logger.error(f'Request method: {request.method}')
        if request.method == 'POST':
            logger.error(f'Form keys: {list(request.form.keys())}')
            logger.error(f'CSRF token in form: {"csrf_token" in request.form}')
        return {'error': 'CSRF token validation failed', 'details': str(e.description)}, 400

    # Root redirect to admin
    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('admin.dashboard'))

    # Create tables
    with app.app_context():
        from app import models  # noqa: F401
        database_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '') or ''

        if database_uri.startswith('postgresql'):
            lock_id = 735017  # Arbitrary app-level advisory lock key
            with db.engine.begin() as connection:
                connection.execute(text('SELECT pg_advisory_lock(:lock_id)'), {'lock_id': lock_id})
                try:
                    db.metadata.create_all(bind=connection)
                finally:
                    connection.execute(text('SELECT pg_advisory_unlock(:lock_id)'), {'lock_id': lock_id})
            # Run column migrations OUTSIDE the advisory-locked transaction so
            # each ALTER TABLE owns its own short transaction and cannot
            # deadlock with concurrent queries from the Telethon worker.
            _run_column_migrations(None)
        else:
            db.create_all()
            _run_column_migrations(None)

        _bootstrap_fresh_database(app)
        _ensure_required_config_keys(app)

    # CLI commands
    register_cli_commands(app)

    return app


def register_cli_commands(app):

    @app.cli.command('create-admin')
    @click.option('--username', prompt=True)
    @click.option('--email', prompt=True)
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(username, email, password):
        """Create an admin user."""
        from app.models import User
        if User.query.filter_by(username=username).first():
            click.echo(f'User {username} already exists.')
            return
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=True
        )
        db.session.add(user)
        db.session.commit()
        click.echo(f'Admin user {username} created successfully.')

    @app.cli.command('run-invitations')
    @click.option('--limit', default=10, help='Max invitations to send')
    def run_invitations(limit):
        """Send pending invitations (Module 3)."""
        click.echo(f'Running invitation batch (limit={limit})...')
        # Will be implemented in invitation_service
        from app.services.invitation_service import get_invitation_service
        service = get_invitation_service()
        if service:
            import asyncio
            count = asyncio.run(service.run_invitation_batch(limit=limit))
            click.echo(f'Sent {count} invitations.')
        else:
            click.echo('Invitation service not available.')

    @app.cli.command('run-publisher')
    @click.option('--count', default=3, help='Max posts to publish')
    def run_publisher(count):
        """Fetch and publish content (Module 4)."""
        click.echo(f'Running publisher (count={count})...')
        from app.services.publisher_service import get_publisher_service
        service = get_publisher_service()
        if service:
            import asyncio
            published = asyncio.run(service.run_publish_cycle(max_posts=count))
            click.echo(f'Published {published} posts.')
        else:
            click.echo('Publisher service not available.')

    @app.cli.command('backup-session')
    def backup_session():
        """Backup Telethon session to database."""
        click.echo('Backing up Telethon session...')
        from app.services.telegram_client import get_telegram_client_manager
        manager = get_telegram_client_manager()
        if manager:
            manager.save_session_to_db()
            click.echo('Session backed up successfully.')
        else:
            click.echo('No active session to backup.')

    @app.cli.command('snapshot-stats')
    def snapshot_stats():
        """Take daily statistics snapshot."""
        click.echo('Taking stats snapshot...')
        from app.models import (
            DiscoveredChannel, Contact, InvitationLog,
            PublishedPost, StarTransaction
        )
        from datetime import datetime, timedelta
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)

        stats = {
            'channels_total': DiscoveredChannel.query.count(),
            'channels_joined': DiscoveredChannel.query.filter_by(is_joined=True).count(),
            'contacts_total': Contact.query.count(),
            'invitations_sent': InvitationLog.query.count(),
            'posts_published': PublishedPost.query.filter_by(status='published').count(),
        }
        for key, value in stats.items():
            click.echo(f'  {key}: {value}')
