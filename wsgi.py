"""
WSGI entry point for Gunicorn (Production)

This file is used by Render.com and other WSGI servers.
For local development, use: python run.py
"""
import logging
import os
from werkzeug.security import generate_password_hash

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

from app import create_app, db
from app.models import User

app = create_app()

# Initialize default admin user if no admin exists (runs once on first startup)
def init_default_admin():
    """Create a default admin user if no admin users exist in the database."""
    if os.getenv('FLASK_ENV') != 'production':
        return  # Only auto-create on production
    
    try:
        with app.app_context():
            # Check if any admin users exist
            admin_count = User.query.filter_by(is_admin=True).count()
            if admin_count == 0:
                # Check environment variables for initial admin
                init_user = os.getenv('INIT_ADMIN_USER')
                init_email = os.getenv('INIT_ADMIN_EMAIL')
                init_pass = os.getenv('INIT_ADMIN_PASSWORD')
                
                if init_user and init_email and init_pass:
                    # Create admin user from environment variables
                    admin = User(
                        username=init_user,
                        email=init_email,
                        password_hash=generate_password_hash(init_pass),
                        is_admin=True
                    )
                    db.session.add(admin)
                    db.session.commit()
                    logger.info(f'Created default admin user: {init_user}')
                else:
                    logger.warning(
                        'No admin users found. Set INIT_ADMIN_USER, INIT_ADMIN_EMAIL, '
                        'and INIT_ADMIN_PASSWORD environment variables to create one.'
                    )
    except Exception as e:
        logger.error(f'Error initializing default admin: {e}')

# Initialize on startup
try:
    init_default_admin()
except Exception as e:
    logger.warning(f'Admin initialization (non-critical): {e}')

if __name__ == '__main__':
    # This is only for local testing
    # For production, use: gunicorn wsgi:app
    logger.warning('Running in development mode. For production use gunicorn.')
    app.run(host='0.0.0.0', port=5000, debug=False)

