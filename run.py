#!/usr/bin/env python
"""
Unified Application Manager

Runs all modules of the Telegram Automation app in proper sequence:
1. Flask Web Application (Admin Panel)
2. Telethon Background Worker (Telegram Client)
3. Monitors inter-process communication

Usage:
    python run.py              # Run everything
    python run.py --web-only   # Run only Flask
    python run.py --worker-only # Run only Telethon
"""
import os
import sys
import argparse
import threading
import asyncio
import logging
import signal
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('app_manager')


class AppManager:
    """Manages Flask and Telethon processes with proper coordination."""
    
    def __init__(self, web_only=False, worker_only=False):
        self.web_only = web_only
        self.worker_only = worker_only
        self.running = True
        self.web_thread = None
        self.worker_thread = None
        
        # Setup shutdown handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
    
    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown."""
        logger.info(f'Received signal {signum}, shutting down gracefully...')
        self.running = False
        if self.web_thread and self.web_thread.is_alive():
            logger.info('Stopping Flask...')
            self.web_thread.join(timeout=5)
        if self.worker_thread and self.worker_thread.is_alive():
            logger.info('Stopping Telethon worker...')
            self.worker_thread.join(timeout=5)
        logger.info('Application shut down cleanly.')
        sys.exit(0)
    
    def run_flask(self):
        """Run Flask web application in thread."""
        try:
            logger.info('=' * 70)
            logger.info('Starting Flask Web Application (Admin Panel)')
            logger.info('=' * 70)
            
            from app import create_app
            
            app = create_app()
            
            # Use development server for local testing
            # Set to 0.0.0.0 to accept connections from all interfaces
            logger.info('Flask running on http://localhost:5000')
            logger.info('Admin Panel: http://localhost:5000/admin')
            logger.info('Login page: http://localhost:5000/auth/login')
            
            app.run(
                host='0.0.0.0',
                port=5000,
                debug=False,  # Must be False for proper thread handling
                use_reloader=False,  # Must be False - incompatible with threading
                threaded=True
            )
        except Exception as e:
            logger.error(f'Flask error: {e}', exc_info=True)
        finally:
            logger.warning('Flask web application stopped')
    
    def run_telethon(self):
        """Run Telethon background worker in thread."""
        try:
            logger.info('=' * 70)
            logger.info('Starting Telethon Background Worker')
            logger.info('=' * 70)
            
            # Import and run the async main function from telethon_runner
            from telethon_runner import main
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(main())
            except KeyboardInterrupt:
                logger.info('Telethon worker interrupted')
            finally:
                loop.close()
        except Exception as e:
            logger.error(f'Telethon worker error: {e}', exc_info=True)
        finally:
            logger.warning('Telethon background worker stopped')
    
    def start(self):
        """Start all application components."""
        logger.info('Starting Telegram Automation Application Manager')
        logger.info(f'Configuration: web_only={self.web_only}, worker_only={self.worker_only}')
        
        if not self.worker_only:
            # Start Flask in a separate thread
            logger.info('Launching Flask Web Server...')
            self.web_thread = threading.Thread(target=self.run_flask, daemon=False)
            self.web_thread.start()
            time.sleep(2)  # Give Flask time to start
        
        if not self.web_only:
            # Start Telethon worker in a separate thread
            logger.info('Launching Telethon Background Worker...')
            self.worker_thread = threading.Thread(target=self.run_telethon, daemon=False)
            self.worker_thread.start()
            time.sleep(2)  # Give worker time to initialize
        
        logger.info('=' * 70)
        logger.info('✓ APPLICATION STARTED')
        logger.info('=' * 70)
        
        if not self.web_only:
            logger.info('📱 Telegram Automation Admin Panel:')
            logger.info('   Web: http://localhost:5000/admin')
            logger.info('   Login: http://localhost:5000/auth/login')
        
        if not self.worker_only:
            logger.info('🔄 Background Services:')
            logger.info('   - Telegram Client (Telethon)')
            logger.info('   - Discovery Module (finds channels)')
            logger.info('   - Audience Scanner (scans members)')
            logger.info('   - Publisher Module (publishes content)')
            logger.info('   - Invitation Module (sends invites)')
        
        logger.info('')
        logger.info('Press Ctrl+C to stop all services')
        logger.info('=' * 70)
        logger.info('')
        
        # Keep main thread alive
        try:
            if self.web_thread:
                self.web_thread.join()
            if self.worker_thread:
                self.worker_thread.join()
        except KeyboardInterrupt:
            self.handle_shutdown(2, None)


def check_dependencies():
    """Check if all required dependencies are installed."""
    required_simple = [
        'flask',
        'telethon',
        'openai',
        'flask_sqlalchemy',
        'flask_login'
    ]
    
    required_special = {
        'flask_wtf': 'flask_wtf.csrf'
    }
    
    missing = []
    for package in required_simple:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    for package_name, import_path in required_special.items():
        try:
            __import__(import_path)
        except ImportError:
            missing.append(package_name)
    
    if missing:
        logger.error(f'Missing required packages: {", ".join(missing)}')
        logger.error('Install with: pip install -r requirements.txt')
        return False
    
    return True


def check_database():
    """Check if database is initialized."""
    try:
        from app import create_app, db
        from app.models import User
        
        app = create_app()
        with app.app_context():
            # Try to query users table
            User.query.first()
            logger.info('✓ Database initialized and accessible')
            return True
    except Exception as e:
        logger.warning(f'Database check failed: {e}')
        logger.warning('Database will be auto-created on first Flask request')
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Telegram Automation Application Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python run.py                # Start everything (Flask + Telethon)
  python run.py --web-only     # Start only Flask web server
  python run.py --worker-only  # Start only Telethon background worker
  python run.py --check        # Check configuration and dependencies
        '''
    )
    
    parser.add_argument(
        '--web-only',
        action='store_true',
        help='Run only Flask web application'
    )
    parser.add_argument(
        '--worker-only',
        action='store_true',
        help='Run only Telethon background worker'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Check dependencies and configuration'
    )
    
    args = parser.parse_args()
    
    logger.info('Telegram Automation Application Manager v1.0')
    logger.info('=' * 70)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check configuration
    env_required = ['TELEGRAM_API_ID', 'TELEGRAM_API_HASH']
    missing_env = [var for var in env_required if not os.getenv(var)]
    
    if missing_env:
        logger.warning(f'Missing environment variables: {", ".join(missing_env)}')
        logger.info('These are needed for Telegram functionality, but Flask web will still work')
    
    # Check database
    check_database()
    
    logger.info('')
    
    if args.check:
        logger.info('✓ All checks passed!')
        sys.exit(0)
    
    # Start application
    manager = AppManager(
        web_only=args.web_only,
        worker_only=args.worker_only
    )
    
    try:
        manager.start()
    except Exception as e:
        logger.error(f'Fatal error: {e}', exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
