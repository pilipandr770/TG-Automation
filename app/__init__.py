import os
import click
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.security import generate_password_hash

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
csrf = CSRFProtect()

logger = logging.getLogger(__name__)


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

    # Make csrf_token available to all templates via context processor
    @app.context_processor
    def inject_csrf_token():
        """Inject CSRF token into all templates."""
        from flask_wtf.csrf import generate_csrf
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
        db.create_all()

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
