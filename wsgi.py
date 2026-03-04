"""
WSGI entry point for Gunicorn (Production).

By default, this file runs only Flask.
Telethon should run as a separate process/container.
Set ENABLE_EMBEDDED_TELETHON=true only for single-process local debugging.
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
    import time
    
    try:
        logger.info('=' * 70)
        logger.info('🚀 Starting Telethon Background Worker (in background thread)')
        logger.info('=' * 70)
        
        # Small delay to ensure only one worker starts Telethon
        # (helps avoid race conditions when Gunicorn has multiple workers)
        time.sleep(2)
        
        # Import telethon main
        from telethon_runner import main as telethon_main
        
        # Create and run event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            logger.info('📡 Telethon event loop starting...')
            loop.run_until_complete(telethon_main())
        except KeyboardInterrupt:
            logger.info('⏸️  Telethon interrupted by user')
        except Exception as e:
            logger.error(f'❌ Telethon error: {e}', exc_info=True)
            # Don't exit - just log and continue trying
            time.sleep(10)
        finally:
            logger.warning('🔄 Cleaning up Telethon event loop...')
            try:
                loop.close()
            except:
                pass
        
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

                if not (init_user and init_email and init_pass):
                    init_user = os.getenv('DEFAULT_ADMIN_USER', 'admin')
                    init_email = os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@example.com')
                    init_pass = os.getenv('DEFAULT_ADMIN_PASSWORD', 'ChangeMe_2026!')
                    logger.warning(
                        '⚠️  INIT_ADMIN_* is not set. Using fallback default admin credentials. '
                        'Please change the password immediately after login.'
                    )
                
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


# Start embedded Telethon worker only when explicitly enabled.
enable_embedded_telethon = os.getenv('ENABLE_EMBEDDED_TELETHON', 'false').lower() == 'true'

if enable_embedded_telethon:
    logger.info('📡 ENABLE_EMBEDDED_TELETHON=true -> launching Telethon in background thread...')
    telethon_thread = threading.Thread(
        target=run_telethon_background,
        daemon=True,
        name='TelethonWorker-BGThread'
    )
    telethon_thread.start()
else:
    logger.info('Embedded Telethon disabled. Run telethon_runner.py in a separate process/container.')


if __name__ == '__main__':
    # This is only for local testing
    # For production, use: gunicorn wsgi:app
    logger.warning('Running in development mode. For production use gunicorn.')
    app.run(host='0.0.0.0', port=5000, debug=False)



