"""
WSGI entry point for Gunicorn (Production)

This file is used by Render.com and other WSGI servers.
Runs Flask web app + Telethon background worker together.
"""
import logging
import os
import sys
import threading
import asyncio
from werkzeug.security import generate_password_hash

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger('wsgi')

from app import create_app, db
from app.models import User


def run_telethon_background():
    """Run Telethon worker in background thread."""
    try:
        logger.info('=' * 70)
        logger.info('🚀 Starting Telethon Background Worker (in background thread)')
        logger.info('=' * 70)
        
        # Import telethon main
        from telethon_runner import main as telethon_main
        
        # Create and run event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(telethon_main())
        except Exception as e:
            logger.error(f'❌ Telethon error: {e}', exc_info=True)
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f'❌ Telethon background worker fatal error: {e}', exc_info=True)
    finally:
        logger.warning('⏹️  Telethon background worker stopped')


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
                    logger.info(f'✅ Created default admin user: {init_user}')
                else:
                    logger.warning(
                        '⚠️  No admin users found. Set INIT_ADMIN_USER, INIT_ADMIN_EMAIL, '
                        'and INIT_ADMIN_PASSWORD environment variables to create one.'
                    )
    except Exception as e:
        logger.error(f'❌ Error initializing default admin: {e}')


# Initialize admin on startup (non-blocking)
try:
    logger.info('Initializing admin user...')
    init_default_admin()
except Exception as e:
    logger.warning(f'⚠️  Admin initialization (non-critical): {e}')


# Start Telethon background worker in a daemon thread
# This ensures it runs whenever the Flask app is running
logger.info('📡 Launching Telethon worker in background thread...')
telethon_thread = threading.Thread(
    target=run_telethon_background,
    daemon=True,
    name='TelethonWorker-BGThread'
)
telethon_thread.start()
logger.info('✅ Telethon worker thread started as daemon')


if __name__ == '__main__':
    # This is only for local testing
    # For production, use: gunicorn wsgi:app
    logger.warning('Running in development mode. For production use gunicorn.')
    app.run(host='0.0.0.0', port=5000, debug=False)



