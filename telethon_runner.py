"""
Long-running Telethon event loop.
Runs as a Render.com Background Worker (Process 2).

This is the ONLY process that holds an active Telegram connection.
Flask and RQ workers communicate with it via Redis pub/sub.
"""
import os
import sys
import json
import signal
import asyncio
import logging
from datetime import datetime

# Load environment variables first, before any other imports
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('telethon_runner')


async def send_heartbeat(redis_client):
    """Send heartbeat to Redis every 30 seconds."""
    while True:
        try:
            redis_client.set(
                'telethon_worker_heartbeat',
                datetime.utcnow().isoformat(),
                ex=300  # Expire after 5 minutes
            )
        except Exception as e:
            logger.error(f'Heartbeat error: {e}')
        await asyncio.sleep(30)


async def listen_redis_commands(app, redis_client, discovery, audience, invitation, publisher):
    """Listen for on-demand commands from Flask admin via Redis pub/sub."""
    pubsub = redis_client.pubsub()
    pubsub.subscribe('telethon_commands')
    logger.info('Listening for Redis commands...')

    while True:
        try:
            message = pubsub.get_message(timeout=1.0)
            if message and message['type'] == 'message':
                data = json.loads(message['data'])
                action = data.get('action')
                logger.info(f'Received command: {action}')

                with app.app_context():
                    if action == 'run_discovery':
                        await discovery.run_discovery_cycle()
                    elif action == 'run_invitations':
                        limit = data.get('limit', 10)
                        await invitation.run_invitation_batch(limit=limit)
                    elif action == 'run_publisher':
                        max_posts = data.get('max_posts', 3)
                        await publisher.run_publish_cycle(max_posts=max_posts)
                    elif action == 'run_audience_scan':
                        await audience.run_audience_scan()

        except json.JSONDecodeError:
            logger.warning('Invalid JSON in Redis command')
        except Exception as e:
            logger.error(f'Redis command error: {e}')

        await asyncio.sleep(0.5)


async def main():
    logger.info('=' * 70)
    logger.info('TELETHON_RUNNER: Starting main() function')
    logger.info('=' * 70)
    
    # Import Flask app and services
    from app import create_app, db
    from app.services.telegram_client import get_telegram_client_manager
    from app.services.openai_service import get_openai_service
    from app.services.rate_limiter import get_rate_limiter
    from app.services.discovery_service import get_discovery_service
    from app.services.audience_service import get_audience_service
    from app.services.invitation_service import get_invitation_service
    from app.services.publisher_service import get_publisher_service
    from app.services.conversation_service import get_conversation_service
    from app.services.content_fetcher import ContentFetcher

    logger.info('📦 Creating Flask app...')
    app = create_app()

    with app.app_context():
        # Initialize Telegram client
        logger.info('🔐 Initializing Telegram client...')
        client_mgr = get_telegram_client_manager()
        client_mgr.load_session_from_db()
        client = await client_mgr.get_client()

        if not client:
            logger.error('❌ Failed to create Telegram client. Check credentials.')
            return

        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.error('❌ Telegram client not authorized!')
                logger.error('To authenticate, run locally: python telethon_runner.py')
                logger.error('Or set TELEGRAM_SESSION_STRING in .env')
                
                # Check if we're in production (Render)
                if os.getenv('FLASK_ENV') == 'production':
                    logger.warning('⏳ Running on production. Waiting 30 seconds for manual setup...')
                    await asyncio.sleep(30)
                    logger.error('❌ Giving up: No valid Telegram session. Please authenticate locally first.')
                    return
                
                # Interactive authentication (only for local development)
                logger.info('Starting interactive authentication for local development...')
                phone = input('Enter your phone number (with country code, e.g., +1234567890): ').strip()
                
                await client.sign_in(phone)
                logger.info('SMS code sent to your phone. Check Telegram.')
                
                code = input('Enter the SMS code: ').strip()
                
                try:
                    await client.sign_in(code=code)
                except Exception as e:
                    if '2FA' in str(e) or 'Two-steps' in str(e):
                        logger.info('Two-factor authentication detected. Enter your 2FA password.')
                        password = input('Enter your Telegram password: ').strip()
                        try:
                            await client.sign_in(password=password)
                            logger.info('Successfully authenticated with 2FA!')
                        except Exception as e2:
                            logger.error(f'Failed to sign in with 2FA password: {e2}')
                            return
                    else:
                        logger.error(f'Failed to sign in with code: {e}')
                        return
                
                logger.info('Successfully authenticated!')
                client_mgr.save_session_to_db()
            else:
                logger.info('Telegram client already authorized.')
                # Save session after successful connection
                client_mgr.save_session_to_db()

        except Exception as e:
            logger.error(f'Telegram connection error: {e}')
            return

        # Initialize services
        logger.info('⚙️  Initializing services...')
        rate_limiter = get_rate_limiter()
        logger.info('✅ Rate limiter initialized')
        
        openai_service = get_openai_service()
        logger.info('✅ OpenAI service initialized')
        
        content_fetcher = ContentFetcher()
        logger.info('✅ Content fetcher initialized')

        discovery = get_discovery_service()
        logger.info('✅ Discovery service initialized')
        
        audience = get_audience_service()
        logger.info('✅ Audience service initialized')
        
        invitation = get_invitation_service(client_mgr, rate_limiter)
        logger.info('✅ Invitation service initialized')
        
        publisher = get_publisher_service(client_mgr, openai_service, content_fetcher)
        logger.info('✅ Publisher service initialized')
        
        conversation = get_conversation_service(client_mgr, openai_service)
        logger.info('✅ Conversation service initialized')

        # Register event handlers for Module 5 (incoming messages, payments)
        conversation.register_handlers(client)
        logger.info('Event handlers registered.')

        # Setup Redis for heartbeat and commands
        redis_client = None
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            try:
                import redis
                redis_client = redis.from_url(redis_url)
                redis_client.ping()
                logger.info('Redis connected.')
            except Exception as e:
                logger.warning(f'Redis not available: {e}. Running without Redis.')
                redis_client = None

        # Graceful shutdown handler
        shutdown_event = asyncio.Event()

        def handle_shutdown(signum, frame):
            logger.info(f'Received signal {signum}, shutting down gracefully...')
            shutdown_event.set()

        # Only register signal handlers if running in main thread
        # (signal handlers cannot be registered from background threads)
        import threading
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, handle_shutdown)
            signal.signal(signal.SIGINT, handle_shutdown)
            logger.info('Signal handlers registered')
        else:
            logger.info('Running in background thread - signal handlers managed by run.py')

        # Start background tasks
        tasks = []

        # Module 1: Continuous discovery
        logger.info('🔍 Starting Module 1: Discovery Service')
        tasks.append(asyncio.create_task(
            run_with_app_context(app, discovery.run_forever)
        ))

        # Module 2: Continuous audience scanning
        logger.info('👥 Starting Module 2: Audience Service')
        tasks.append(asyncio.create_task(
            run_with_app_context(app, audience.run_forever)
        ))

        # Module 3: Continuous content publishing
        logger.info('📢 Starting Module 3: Publisher Service')
        tasks.append(asyncio.create_task(
            run_with_app_context(app, publisher.run_forever)
        ))

        # Module 4: Continuous invitation sending
        logger.info('💌 Starting Module 4: Invitation Service')
        invitation_task = asyncio.create_task(
            run_with_app_context(app, invitation.run_forever)
        )
        tasks.append(invitation_task)

        logger.info(f'✅ All {len(tasks)} background modules started successfully!')
        logger.info(f'🎯 Discovery (Module 1): Searching for channels by keywords')
        logger.info(f'👁️  Audience (Module 2): Scanning messages and analyzing contacts')
        logger.info(f'✉️  Invitations (Module 4): Sending invitation messages')
        logger.info(f'📝 Publisher (Module 3): Publishing content to target channel')
        logger.info(f'💬 Conversation (Module 5): Listening for incoming private messages')

        # Heartbeat
        if redis_client:
            tasks.append(asyncio.create_task(send_heartbeat(redis_client)))
            # Redis command listener
            tasks.append(asyncio.create_task(
                listen_redis_commands(app, redis_client, discovery, audience,
                                      invitation, publisher)
            ))

        logger.info(f'Started {len(tasks)} background tasks. Running...')

        # Start Telethon client event loop to listen for incoming messages
        # CRITICAL: client.run_until_disconnected() must run to process updates
        logger.info('🎯 Starting Telethon event listener for incoming message handling...')
        
        async def client_event_loop():
            """Wrapper to ensure client properly listens for updates."""
            try:
                logger.info('💬 Telethon event listener started - waiting for messages...')
                await client.run_until_disconnected()
            except Exception as e:
                logger.error(f'❌ Telethon event loop error: {e}', exc_info=True)
        
        client_task = asyncio.create_task(client_event_loop())
        tasks.append(client_task)

        logger.info('=' * 70)
        logger.info('🎉 TELETHON WORKER FULLY STARTED AND RUNNING!')
        logger.info('=' * 70)
        logger.info('📊 Status:')
        logger.info('  🔍 Module 1 Discovery: Searching channels by keywords')
        logger.info('  👥 Module 2 Audience: Scanning messages for target audience')
        logger.info('  💌 Module 3 Invitations: Ready to send invitations')
        logger.info('  📢 Module 4 Publisher: Ready to publish content')
        logger.info('  💬 Module 5 Conversation: Listening for private messages')
        logger.info('=' * 70)

        # Monitor all tasks - don't exit if one fails, just log it
        logger.info('Monitoring background tasks...')
        while True:
            try:
                # Check all tasks
                for task in tasks:
                    if task.done():
                        try:
                            exc = task.exception()
                            if exc:
                                logger.error(f'❌ Task failed: {exc}')
                                logger.warning(f'🔄 A background task failed. Continuing...')
                        except asyncio.CancelledError:
                            pass
                
                # Sleep briefly then check again
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                logger.info('⏹️  Task monitoring cancelled')
                break
            except Exception as e:
                logger.error(f'Task monitoring error: {e}', exc_info=True)
                await asyncio.sleep(5)

        # Cleanup
        logger.info('Shutting down tasks...')
        for task in tasks:
            if not task.done():
                task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

        # Save session before exit
        client_mgr.save_session_to_db()
        await client.disconnect()
        logger.info('Telethon worker shut down cleanly.')


async def run_with_app_context(app, coro_func):
    """Run an async function within Flask app context."""
    with app.app_context():
        try:
            logger.info(f'Starting service: {coro_func.__name__}')
            await coro_func()
        except asyncio.CancelledError:
            logger.info(f'Service cancelled: {coro_func.__name__}')
            pass
        except Exception as e:
            logger.error(f'Task error in {coro_func.__name__}: {e}', exc_info=True)
            # Small delay before restarting
            await asyncio.sleep(5)
            # Retry once
            try:
                logger.info(f'Restarting service: {coro_func.__name__}')
                await coro_func()
            except Exception as e2:
                logger.error(f'Task error (retry) in {coro_func.__name__}: {e2}', exc_info=True)


if __name__ == '__main__':
    logger.info('Starting Telethon worker...')
    asyncio.run(main())
