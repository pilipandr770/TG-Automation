"""
Integration guide for TelegramDispatcher.

This module shows how to use the dispatcher to prevent orchestration issues.
"""

import asyncio
import logging
from app.services.telegram_dispatcher import (
    TelegramDispatcher,
    TelegramTask,
    TaskType,
    get_telegram_dispatcher
)

logger = logging.getLogger(__name__)


class DispatcherIntegrationExample:
    """
    Example of how to use TelegramDispatcher in your services.
    
    OLD PATTERN (❌ AVOIDED):
        async def search_channels(keyword):
            client = await client_manager.get_client()
            return await client.get_dialogs()  # Direct API call
    
    NEW PATTERN (✅ CORRECT):
        async def search_channels(keyword):
            dispatcher = await get_telegram_dispatcher()
            task = TelegramTask(
                task_type=TaskType.SEARCH,
                operation=self._search_impl,  # Method, not direct API
                args=(keyword,)
            )
            result = await dispatcher.submit(task)
            return result.data if result.success else None
    """
    
    async def search_channels_example(self, keyword: str):
        """Example: Search channels via dispatcher."""
        dispatcher = await get_telegram_dispatcher()
        
        # Define the operation (not async, dispatcher handles it)
        async def search_op():
            client = await self._get_client()
            return await client.get_dialogs()
        
        task = TelegramTask(
            task_type=TaskType.SEARCH,
            operation=search_op,
            timeout=30.0
        )
        
        result = await dispatcher.submit(task)
        
        if result.success:
            logger.info(f'✅ Found {len(result.data)} channels')
            return result.data
        else:
            logger.error(f'❌ Search failed: {result.error}')
            return []
    
    async def join_channel_example(self, channel_id: int):
        """Example: Join channel via dispatcher."""
        dispatcher = await get_telegram_dispatcher()
        
        async def join_op():
            client = await self._get_client()
            return await client.get_entity(channel_id)
        
        task = TelegramTask(
            task_type=TaskType.JOIN,
            operation=join_op,
            timeout=10.0
        )
        
        result = await dispatcher.submit(task)
        return result.success


# ──────────────────────────────────────────────────────────────────────────────

class ServiceDispatcherPattern:
    """
    How to refactor a service to use dispatcher.
    
    This is the pattern for all services (Discovery, Audience, etc.)
    """
    
    def __init__(self, client_manager):
        self._client_manager = client_manager
        self._dispatcher: Optional[TelegramDispatcher] = None
    
    async def _get_dispatcher(self) -> TelegramDispatcher:
        """Lazy load dispatcher."""
        if self._dispatcher is None:
            self._dispatcher = await get_telegram_dispatcher()
        return self._dispatcher
    
    async def _dispatch_telegram_op(
        self,
        task_type: TaskType,
        operation,
        *args,
        timeout: float = 30.0,
        **kwargs
    ):
        """Helper to submit any Telegram operation to dispatcher."""
        dispatcher = await self._get_dispatcher()
        
        task = TelegramTask(
            task_type=task_type,
            operation=operation,
            args=args,
            kwargs=kwargs,
            timeout=timeout
        )
        
        return await dispatcher.submit(task)
    
    async def example_method(self):
        """Example of using the dispatcher pattern."""
        # Instead of:
        # client = await self._client_manager.get_client()
        # await client.search_global(keyword)
        
        # Do this:
        result = await self._dispatch_telegram_op(
            task_type=TaskType.SEARCH,
            operation=self._search_impl,  # Your method
            "keyword_here",  # Args
            timeout=30.0
        )
        
        return result


# ──────────────────────────────────────────────────────────────────────────────

class CoordinatorDispatcherIntegration:
    """
    How CoordinatorService should initialize the dispatcher.
    
    This goes in telethon_runner.py main() function.
    """
    
    @staticmethod
    async def setup_dispatcher():
        """Initialize dispatcher before starting services."""
        logger.info('🚀 Initializing TelegramDispatcher...')
        
        dispatcher = await get_telegram_dispatcher()
        
        # Start the worker loop
        await dispatcher.start()
        
        logger.info('✅ TelegramDispatcher ready')
        
        return dispatcher
    
    @staticmethod
    async def shutdown_dispatcher():
        """Gracefully shutdown dispatcher."""
        logger.info('🛑 Shutting down TelegramDispatcher...')
        
        dispatcher = await get_telegram_dispatcher()
        await dispatcher.stop()
        
        stats = dispatcher.get_stats()
        logger.info(f'📊 Final stats: {stats}')


# ──────────────────────────────────────────────────────────────────────────────

MIGRATION_CHECKLIST = """
MIGRATION CHECKLIST: Move service to use TelegramDispatcher

For each service (Discovery, Audience, Publisher, etc.):

1. ✅ Add to __init__:
    self._dispatcher = None  # Lazy loaded

2. ✅ Add helper method:
    async def _get_dispatcher(self) -> TelegramDispatcher:
        if self._dispatcher is None:
            self._dispatcher = await get_telegram_dispatcher()
        return self._dispatcher

3. ✅ Add dispatch helper:
    async def _dispatch_telegram_op(
        self, task_type, operation, *args, timeout=30.0, **kwargs
    ):
        dispatcher = await self._get_dispatcher()
        task = TelegramTask(
            task_type=task_type,
            operation=operation,
            args=args,
            kwargs=kwargs,
            timeout=timeout
        )
        return await dispatcher.submit(task)

4. ✅ Replace direct client calls:
    # OLD:
    client = await self._client_manager.get_client()
    result = await client.some_api_call()
    
    # NEW:
    result = await self._dispatch_telegram_op(
        TaskType.CUSTOM,
        self._some_api_call_impl
    )

5. ✅ Test with dispatcher running in telethon_runner

6. ✅ Monitor logs for [DISPATCH] messages
"""
