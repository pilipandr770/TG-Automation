"""
ADMIN_ROUTES REFACTORING GUIDE

This file shows the exact changes needed for admin_routes.py to use
TelegramDispatcher instead of creating separate TelegramClient instances.

Key Issue: Lines ~215-330 create fresh TelegramClient in asyncio.run() event loop.
This conflicts with the singleton manager and main telethon_runner.py loop.

Solution: Refactor to submit tasks to TelegramDispatcher.
"""

# ══════════════════════════════════════════════════════════════════════════════
# BEFORE (CURRENT - PROBLEMATIC)
# ══════════════════════════════════════════════════════════════════════════════

BEFORE_CODE = '''
@admin_bp.route('/channels/manual-join', methods=['POST'])
@login_required
def join_channel_manual():
    """
    Manually join a channel by username or link.
    Uses a fresh TelegramClient for each request to avoid event loop conflicts.
    """
    import asyncio
    from telethon.sessions import StringSession
    from telethon import TelegramClient  # ❌ PROBLEM: Direct import
    from app.models import TelegramSession
    
    channel_input = request.form.get('channel_input', '').strip()
    logger.info(f'join_channel_manual: channel_input="{channel_input}"')
    
    if not channel_input:
        flash('Пожалуйста, введите username или ссылку на канал', 'warning')
        return redirect(url_for('admin.channels'))
    
    async def manual_join_async():
        """Async function running in fresh event loop with new TelegramClient."""
        try:
            api_id = int(os.getenv('TELEGRAM_API_ID', 0))
            api_hash = os.getenv('TELEGRAM_API_HASH', '')
            
            if not api_id or not api_hash:
                return None, 'Telegram API credentials not configured'
            
            # Load session from database
            session_record = TelegramSession.query.filter_by(
                session_name='default', is_active=True
            ).first()
            
            if not session_record or not session_record.session_string:
                logger.warning('join_channel_manual: No session in database')
                return None, 'Телеграм сессия не найдена. Требуется новая аутентификация.'
            
            logger.info('join_channel_manual: Creating fresh TelegramClient')
            session = StringSession(session_record.session_string)
            client = TelegramClient(session, api_id, api_hash)  # ❌ Creates separate client!
            
            try:
                await client.connect()
                logger.info('join_channel_manual: Client connected')
                
                # Get the channel entity
                logger.info(f'join_channel_manual: Resolving entity "{channel_input}"')
                channel = await client.get_entity(channel_input)
                logger.info(f'join_channel_manual: Resolved to id={channel.id}')
                
                # ... rest of the logic ...
                
                return discovered, f'✓ Канал добавлен: {title} ({subscribers} подписчиков)'
            
            finally:
                if client.is_connected():
                    await client.disconnect()
                    logger.info('join_channel_manual: Client disconnected')
        
        except Exception as e:
            logger.exception(f'join_channel_manual: Exception: {e}')
            return None, f'Ошибка: {str(e)[:100]}'
    
    try:
        # ❌ PROBLEM: Creates new event loop, conflicts with main loop
        result = asyncio.run(manual_join_async())
        
        if result:
            channel, message = result
            if channel:
                flash(message, 'success')
            else:
                flash(message, 'warning')
        
    except Exception as e:
        logger.exception(f'join_channel_manual: Uncaught exception: {e}')
        flash(f'Ошибка: {str(e)[:80]}', 'danger')
    
    return redirect(url_for('admin.channels'))
'''

# ══════════════════════════════════════════════════════════════════════════════
# AFTER (REFACTORED - CORRECT)
# ══════════════════════════════════════════════════════════════════════════════

AFTER_CODE = '''
@admin_bp.route('/channels/manual-join', methods=['POST'])
@login_required
def join_channel_manual():
    """
    Manually join a channel by username or link.
    Submits task to TelegramDispatcher instead of creating duplicate client.
    """
    from app.services.telegram_dispatcher import (
        get_telegram_dispatcher,
        TelegramTask,
        TaskType
    )
    
    channel_input = request.form.get('channel_input', '').strip()
    logger.info(f'join_channel_manual: channel_input="{channel_input}"')
    
    if not channel_input:
        flash('Пожалуйста, введите username или ссылку на канал', 'warning')
        return redirect(url_for('admin.channels'))
    
    async def dispatch_join_channel():
        """Submit channel join to dispatcher queue."""
        dispatcher = await get_telegram_dispatcher()
        
        # Create task with the actual operation
        task = TelegramTask(
            task_type=TaskType.JOIN,
            operation=_join_channel_impl,  # See below
            args=(channel_input,),
            timeout=30.0
        )
        
        result = await dispatcher.submit(task)
        return result
    
    try:
        # Use the application's asyncio context instead of creating new loop
        from app.services.telegram_client import get_telegram_client_manager
        
        # Get access to the running event loop (from telethon_runner.py)
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # We have an event loop, we can use it
            import concurrent.futures
            import threading
            
            # Submit to the running loop from a thread
            future = asyncio.run_coroutine_threadsafe(
                dispatch_join_channel(),
                loop
            )
            task_result = future.result(timeout=35.0)
        except RuntimeError:
            # No running loop, create one (for testing)
            task_result = asyncio.run(dispatch_join_channel())
        
        if task_result and task_result.success:
            discovered = task_result.data
            flash(f'✓ Канал добавлен: {discovered["title"]}', 'success')
        else:
            error_msg = task_result.error if task_result else 'Unknown error'
            flash(f'Ошибка: {error_msg[:80]}', 'warning')
        
    except Exception as e:
        logger.exception(f'join_channel_manual: Uncaught exception: {e}')
        flash(f'Ошибка: {str(e)[:80]}', 'danger')
    
    return redirect(url_for('admin.channels'))


async def _join_channel_impl(channel_input: str):
    """
    ACTUAL implementation - runs in dispatcher's event loop.
    This is what gets submitted as the operation.
    """
    from app.models import TelegramSession, DiscoveredChannel
    from telethon.sessions import StringSession
    from telethon import types, functions
    
    api_id = int(os.getenv('TELEGRAM_API_ID', 0))
    api_hash = os.getenv('TELEGRAM_API_HASH', '')
    
    if not api_id or not api_hash:
        raise ValueError('Telegram API credentials not configured')
    
    # Load session from database
    session_record = TelegramSession.query.filter_by(
        session_name='default', is_active=True
    ).first()
    
    if not session_record or not session_record.session_string:
        raise ValueError('Телеграм сессия не найдена. Требуется новая аутентификация.')
    
    logger.info(f'_join_channel_impl: Resolving "{channel_input}"')
    
    # Use the singleton client manager
    client_mgr = get_telegram_client_manager()
    client = await client_mgr.get_client()
    
    try:
        # Get the channel entity
        channel = await client.get_entity(channel_input)
        logger.info(f'_join_channel_impl: Resolved to id={channel.id}')
        
        # Check if already in database
        existing = DiscoveredChannel.query.filter_by(
            telegram_id=channel.id
        ).first()
        
        if existing:
            logger.info(f'_join_channel_impl: Channel already in DB: {existing.title}')
            raise ValueError(f'Канал уже добавлен: {existing.title}')
        
        # Try to join the channel
        join_status = 'found'
        try:
            logger.info(f'_join_channel_impl: Attempting JoinChannelRequest')
            await client(functions.channels.JoinChannelRequest(channel=channel))
            join_status = 'joined'
            logger.info(f'_join_channel_impl: Successfully joined')
        except Exception as join_e:
            logger.info(f'_join_channel_impl: Join failed (non-critical): {join_e}')
        
        # Extract channel info
        title = getattr(channel, 'title', 'Unknown')
        username = getattr(channel, 'username', None)
        about = getattr(channel, 'about', '')
        subscribers = getattr(channel, 'participants_count', 0) or 0
        has_comments = getattr(channel, 'megagroup', False) or getattr(channel, 'gigagroup', False)
        
        # Determine channel type
        channel_type = 'channel'
        if getattr(channel, 'megagroup', False) or getattr(channel, 'gigagroup', False):
            channel_type = 'supergroup'
        elif isinstance(channel, types.Chat):
            channel_type = 'group'
        
        logger.info(f'_join_channel_impl: Saving - title={title}, type={channel_type}')
        
        # Save to database
        discovered = DiscoveredChannel(
            telegram_id=channel.id,
            username=username,
            title=title,
            description=about,
            channel_type=channel_type,
            subscriber_count=subscribers,
            has_comments=has_comments,
            is_joined=(join_status == 'joined'),
            join_date=datetime.utcnow() if join_status == 'joined' else None,
            status=join_status,
            topic_match_score=1.0,
        )
        
        db.session.add(discovered)
        db.session.commit()
        logger.info(f'_join_channel_impl: Saved to DB with id={discovered.id}')
        
        # Return serializable data (not ORM object)
        return {
            'title': discovered.title,
            'username': discovered.username,
            'type': discovered.channel_type,
            'subscribers': discovered.subscriber_count,
            'id': discovered.id
        }
    
    except Exception as e:
        logger.exception(f'_join_channel_impl: Exception: {e}')
        raise
'''

# ══════════════════════════════════════════════════════════════════════════════
# COMPARISON & KEY CHANGES
# ══════════════════════════════════════════════════════════════════════════════

COMPARISON = '''
┌─ BEFORE (Problematic) ──────────────────────────────────────────────────┐
│                                                                           │
│ 1. ❌ Direct import: from telethon import TelegramClient                │
│ 2. ❌ Creates new client: TelegramClient(session, api_id, api_hash)     │
│ 3. ❌ New event loop: asyncio.run(manual_join_async())                  │
│ 4. ❌ Blocks request until complete (no parallelism)                    │
│ 5. ❌ Conflicts with telethon_runner.py main loop                       │
│ 6. ❌ Session management separated from singleton                        │
│                                                                           │
│ RESULT: Multiple client instances, lock contention, timing issues       │
└─────────────────────────────────────────────────────────────────────────┘

┌─ AFTER (Correct) ───────────────────────────────────────────────────────┐
│                                                                           │
│ 1. ✅ Import dispatcher: from app.services.telegram_dispatcher import   │
│ 2. ✅ Submit task: dispatcher.submit(TelegramTask(...))                 │
│ 3. ✅ Reuse event loop: asyncio.get_running_loop() or run_coroutine    │
│ 4. ✅ Execution serialized through queue                                │
│ 5. ✅ Integrates with telethon_runner.py main loop                      │
│ 6. ✅ Session management via singleton client manager                   │
│                                                                           │
│ RESULT: Single client, serialized access, no conflicts, stable          │
└─────────────────────────────────────────────────────────────────────────┘
'''

# ══════════════════════════════════════════════════════════════════════════════
# KEY DIFFERENCES EXPLAINED
# ══════════════════════════════════════════════════════════════════════════════

KEY_CHANGES = '''
CHANGE #1: Remove Direct TelegramClient Creation
────────────────────────────────────────────────

❌ OLD:
    import asyncio
    from telethon import TelegramClient
    
    client = TelegramClient(session, api_id, api_hash)
    await client.connect()
    result = await client.get_entity(...)

✅ NEW:
    from app.services.telegram_dispatcher import get_telegram_dispatcher
    
    dispatcher = await get_telegram_dispatcher()
    task = TelegramTask(
        task_type=TaskType.JOIN,
        operation=_join_channel_impl,
        args=(channel_input,)
    )
    result = await dispatcher.submit(task)


CHANGE #2: Use Dispatcher to Submit Operations
───────────────────────────────────────────────

❌ OLD:
    async def manual_join_async():
        client = TelegramClient(...)
        await client.connect()
        # ... do work ...
        await client.disconnect()
    
    result = asyncio.run(manual_join_async())

✅ NEW:
    async def dispatch_join_channel():
        dispatcher = await get_telegram_dispatcher()
        task = TelegramTask(
            task_type=TaskType.JOIN,
            operation=_join_channel_impl,
        )
        return await dispatcher.submit(task)
    
    # Use running loop instead of creating new one
    result = asyncio.run_coroutine_threadsafe(
        dispatch_join_channel(),
        loop
    ).result(timeout=35.0)


CHANGE #3: Move Raw Implementation to Separate Function
────────────────────────────────────────────────────────

❌ OLD (all logic in async handler):
    async def manual_join_async():
        client = TelegramClient(...)
        channel = await client.get_entity(channel_input)
        # ... 50 lines of channel logic ...
        db.session.add(discovered)
        db.session.commit()

✅ NEW (logic extracted to implementation function):
    async def _join_channel_impl(channel_input: str):
        # Same logic, but receives channel_input as parameter
        # Uses get_telegram_client_manager() instead of creating client
        client = await get_telegram_client_manager().get_client()
        channel = await client.get_entity(channel_input)
        # ... same 50 lines ...
        return serialized_data  # Return dict, not ORM object


CHANGE #4: Handle Event Loop Integration
──────────────────────────────────────────

❌ OLD (always creates new loop):
    result = asyncio.run(manual_join_async())

✅ NEW (reuses existing loop if available):
    try:
        loop = asyncio.get_running_loop()  # Telethon's loop
        future = asyncio.run_coroutine_threadsafe(
            dispatch_join_channel(),
            loop
        )
        result = future.result(timeout=35.0)
    except RuntimeError:
        # No loop, create one (for testing)
        result = asyncio.run(dispatch_join_channel())


CHANGE #5: Return Serializable Data
────────────────────────────────────

❌ OLD:
    return discovered  # ORM object, not serializable

✅ NEW:
    return {
        'title': discovered.title,
        'username': discovered.username,
        'type': discovered.channel_type,
        'subscribers': discovered.subscriber_count,
        'id': discovered.id
    }
'''

# ══════════════════════════════════════════════════════════════════════════════
# STEP-BY-STEP IMPLEMENTATION
# ══════════════════════════════════════════════════════════════════════════════

IMPLEMENTATION_STEPS = '''
STEP-BY-STEP: Refactor admin_routes.py

1. IDENTIFY all routes that use TelegramClient directly
   ✓ Find: /channels/manual-join (lines 215-330)
   ✓ Find: Any other routes that import TelegramClient
   ✓ Search: "from telethon import TelegramClient"
   ✓ Search: "TelegramClient("

2. FOR EACH route, extract the operation into _<name>_impl() function
   ✓ Take the async logic from nested async def
   ✓ Replace `client = TelegramClient(...)` with
     `client = await get_telegram_client_manager().get_client()`
   ✓ Replace `await client.connect()` + `await client.disconnect()`
     with just getting/using the client (manager handles lifecycle)
   ✓ Make sure function is async
   ✓ Make sure function accepts parameters it needs
   ✓ Make sure function returns serializable data (not ORM objects)

3. REPLACE the old nested async function with dispatcher submission
   ✓ Remove: async def manual_join_async():
   ✓ Remove: asyncio.run(manual_join_async())
   ✓ Remove: Direct TelegramClient(...) creation
   ✓ Add: from app.services.telegram_dispatcher import ...
   ✓ Add: dispatcher.submit(TelegramTask(...))
   ✓ Add: event loop reuse logic (try/except RuntimeError)

4. TEST each route
   ✓ Run telethon_runner.py in one terminal
   ✓ Open Flask web server in another
   ✓ Use route, check logs for [DISPATCH] messages
   ✓ Verify operation completed
   ✓ No errors about multiple clients

5. VERIFY in logs
   ✓ See: "[DISPATCH] Task accepted"
   ✓ See: "[DISPATCH] Task started"
   ✓ See: "[DISPATCH] Task completed - success"
   ✓ No: "TelegramClient is not connected" errors
   ✓ No: "Another session is using this client" errors
'''

# ══════════════════════════════════════════════════════════════════════════════
# POTENTIAL ROUTES THAT NEED FIXING
# ══════════════════────────────════════════════════════════════════════════════

ROUTES_TO_AUDIT = '''
AUDIT CHECKLIST: Other admin_routes.py routes that use TelegramClient

Search admin_routes.py for these patterns:

[ ] "from telethon import TelegramClient"
    - Line: ___
    - Route: ___
    - Action: Remove import if not needed, or move to implementation

[ ] "TelegramClient("
    - Line: ___
    - Context: ___
    - Action: Extract to _*_impl() function, use dispatcher

[ ] "asyncio.run("
    - Line: ___
    - Context: ___
    - Action: Replace with dispatcher if doing Telegram operations

[ ] ".connect()"
    - Line: ___
    - Context: ___
    - Action: Remove (client lifecycle handled by manager)

[ ] ".disconnect()"
    - Line: ___
    - Context: ___
    - Action: Remove (client lifecycle handled by manager)

[ ] "get_dialogs()"
    - Line: ___
    - Context: ___
    - Action: Move to _*_impl(), submit via dispatcher

[ ] "get_entity("
    - Line: ___
    - Context: ___
    - Action: Move to _*_impl(), submit via dispatcher

[ ] "send_message("
    - Line: ___
    - Context: ___
    - Action: Move to _*_impl(), submit via dispatcher

[ ] "search_global("
    - Line: ___
    - Context: ___
    - Action: Move to _*_impl(), submit via dispatcher

RESULT: All direct client operations should be gone.
        All operations should go through dispatcher.
'''

print("=" * 80)
print("ADMIN_ROUTES REFACTORING GUIDE")
print("=" * 80)
print()
print(COMPARISON)
print()
print(KEY_CHANGES)
print()
print(IMPLEMENTATION_STEPS)
print()
print(ROUTES_TO_AUDIT)
