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
    logger.info('CODE VERSION: async-openai-client-v6 (2026-03-23)')
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
    from app.services.coordinator_service import get_coordinator_service
    from app.services.content_fetcher import ContentFetcher

    logger.info('📦 Creating Flask app...')
    app = create_app()

    with app.app_context():
        # Initialize Telegram client
        logger.info('🔐 Initializing Telegram client...')
        client_mgr = get_telegram_client_manager()

        async def _try_connect_and_authorize(session_source: str) -> bool:
            """Attempt to connect and verify authorization. Returns True on success."""
            try:
                client = await client_mgr.get_client()
                if not client:
                    return False
                if not client.is_connected():
                    await client.connect()
                authorized = await client.is_user_authorized()
                if authorized:
                    logger.info('✅ Telegram client authorized via %s session.', session_source)
                    client_mgr.save_session_to_db()
                    return True
                logger.warning('⚠️  Session from %s loaded but not authorized.', session_source)
                return False
            except Exception as e:
                logger.warning('⚠️  Connection attempt with %s session failed: %s', session_source, str(e)[:120])
                return False

        # ── Strategy 1: Try .env session first (always the intended configuration) ──
        authorized = False
        env_session = os.getenv('TELEGRAM_SESSION_STRING', '').strip()
        if env_session:
            logger.info('🔑 Trying .env TELEGRAM_SESSION_STRING ...')
            client_mgr._instance = None  # reset singleton so a fresh client is built
            client_mgr._session_string = env_session
            client_mgr.client = None
            authorized = await _try_connect_and_authorize('.env')

        # ── Strategy 2: Fall back to DB session if env didn't work ──
        if not authorized:
            logger.info('🔑 Trying session from database ...')
            # Reset client so a new one is created with the DB session
            client_mgr._session_string = None
            client_mgr.client = None
            loaded = client_mgr.load_session_from_db()
            if loaded:
                authorized = await _try_connect_and_authorize('database')

        if not authorized:
            logger.error('❌ Telegram client not authorized!')
            logger.error('Please set a valid TELEGRAM_SESSION_STRING in your .env / environment variables.')
            logger.error('Run locally with: python scripts/telegram_auth_session.py  (or python telethon_runner.py)')
            if os.getenv('FLASK_ENV') == 'production':
                logger.warning('⏳ No valid Telegram session — waiting 60 s before exit to allow log collection.')
                await asyncio.sleep(60)
            return

        client = await client_mgr.get_client()
        if not client:
            logger.error('❌ Could not obtain Telegram client after authorization check.')
            return

        # Initialize services
        logger.info('⚙️  Initializing services...')
        rate_limiter = get_rate_limiter()
        logger.info('✅ Rate limiter initialized')
        
        openai_service = get_openai_service()
        openai_service._app = app  # allow executor threads to reuse the running Flask app context
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

        # Create coordinator with all services
        coordinator = get_coordinator_service(discovery, audience, conversation, publisher, invitation)
        logger.info('✅ Coordinator service initialized')

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

        # ────────────────────────────────────────────────────────────────
        # COORDINATOR: Orchestrates all 5 modules in round-robin sequence
        # ────────────────────────────────────────────────────────────────
        # Instead of 5 concurrent infinite loops (which interfere with each other),
        # the coordinator runs them in strict order:
        # 1. Discovery → 2. Audience → 3. Conversation (event-driven) → 4. Publisher → 5. Invitations
        # Each task completes before the next starts, preventing resource contention
        
        logger.info('🎯 Starting Coordinator (round-robin orchestration of 5 modules)')
        tasks.append(asyncio.create_task(
            run_with_app_context(app, coordinator.run_coordinator)
        ))

        logger.info(f'✅ Coordinator started successfully!')
        logger.info(f'📋 Execution sequence per cycle:')
        logger.info(f'   1️⃣ Discovery (Module 1): Search & join channels')
        logger.info(f'   2️⃣ Audience (Module 2): Scan & analyze contacts')
        logger.info(f'   3️⃣ Conversation (Module 5): Listen for incoming PMs (event-driven)')
        logger.info(f'   4️⃣ Publisher (Module 3): Publish content to channel')
        logger.info(f'   5️⃣ Invitations (Module 4): Send PMs to contacts')
        logger.info(f'   ↻ Repeat every 60+ seconds')

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
