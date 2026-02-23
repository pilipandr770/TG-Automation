"""
TelegramDispatcher: Centralized Telegram operations orchestrator.

This ensures:
- Single TelegramClient instance
- Single asyncio event loop (main)
- Serialized Telegram API calls via asyncio.Queue
- Type-safe task execution with results
- Proper error handling and recovery
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of Telegram operations."""
    SEARCH = "search"
    JOIN = "join"
    PARSE = "parse"
    INVITE = "invite"
    POST = "post"
    REPLY = "reply"
    CUSTOM = "custom"


@dataclass
class TelegramTask:
    """Encapsulates a single Telegram operation."""
    task_type: TaskType
    operation: Callable
    args: tuple = ()
    kwargs: dict = None
    timeout: float = 30.0
    
    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


@dataclass
class TaskResult:
    """Result of a Telegram task execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    task_type: Optional[TaskType] = None


class TelegramDispatcher:
    """
    Central dispatcher for all Telegram operations.
    
    Ensures serialized execution with proper error handling.
    Single instance per application lifecycle.
    """
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __init__(self, max_queue_size: int = 1000):
        """
        Initialize dispatcher.
        
        Args:
            max_queue_size: Maximum pending tasks in queue
        """
        self._task_queue: asyncio.Queue[TelegramTask] = asyncio.Queue(
            maxsize=max_queue_size
        )
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._executed_count = 0
        self._failed_count = 0
        
        logger.info('🚀 TelegramDispatcher initialized')
    
    async def start(self) -> None:
        """Start the dispatcher worker loop."""
        if self._running:
            logger.warning('⚠️  Dispatcher already running')
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info('✅ Dispatcher worker loop started')
    
    async def stop(self) -> None:
        """Gracefully stop the dispatcher."""
        self._running = False
        
        # Wait for pending tasks to complete
        remaining = self._task_queue.qsize()
        if remaining > 0:
            logger.info(f'⏳ Waiting for {remaining} pending tasks to complete...')
            while not self._task_queue.empty():
                await asyncio.sleep(0.1)
        
        if self._worker_task:
            await self._worker_task
        
        logger.info(f'✅ Dispatcher stopped. Executed: {self._executed_count}, Failed: {self._failed_count}')
    
    async def submit(self, task: TelegramTask) -> TaskResult:
        """
        Submit a Telegram task and wait for result.
        
        Args:
            task: TelegramTask to execute
            
        Returns:
            TaskResult with execution result
            
        Raises:
            asyncio.QueueFull if queue is full
            asyncio.TimeoutError if task takes too long
        """
        if not self._running:
            return TaskResult(
                success=False,
                error='Dispatcher not running',
                task_type=task.task_type
            )
        
        # Create a result future for this task
        result_future: asyncio.Future[TaskResult] = asyncio.Future()
        
        # Attach the future to the task so worker can update it
        task._result_future = result_future
        
        try:
            # Submit task to queue (non-blocking, but with timeout)
            self._task_queue.put_nowait(task)
            logger.debug(f'📤 Task queued: {task.task_type.value}')
        except asyncio.QueueFull:
            return TaskResult(
                success=False,
                error='Task queue full',
                task_type=task.task_type
            )
        
        # Wait for result with timeout
        try:
            result = await asyncio.wait_for(
                result_future,
                timeout=task.timeout
            )
            logger.debug(f'📥 Task completed: {result.task_type.value} - {result.success}')
            return result
        except asyncio.TimeoutError:
            return TaskResult(
                success=False,
                error=f'Task timeout (>{task.timeout}s)',
                task_type=task.task_type
            )
    
    async def _worker_loop(self) -> None:
        """Process tasks from queue sequentially."""
        logger.info('[DISPATCHER WORKER] Started')
        
        while self._running:
            try:
                # Wait for next task with timeout to allow graceful shutdown
                task = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0
                )
                
                await self._execute_task(task)
                
            except asyncio.TimeoutError:
                # Queue was empty, retry
                continue
            except Exception as e:
                logger.error(f'[DISPATCHER WORKER] Error: {e}', exc_info=True)
                await asyncio.sleep(0.5)  # Prevent busy loop on errors
        
        logger.info('[DISPATCHER WORKER] Stopped')
    
    async def _execute_task(self, task: TelegramTask) -> None:
        """Execute a single task and set result."""
        result_future = getattr(task, '_result_future', None)
        
        try:
            logger.info(f'⚙️  [DISPATCH] Executing {task.task_type.value}')
            
            # Execute the operation
            if asyncio.iscoroutinefunction(task.operation):
                data = await task.operation(*task.args, **task.kwargs)
            else:
                # Wrap sync function in thread executor to prevent blocking
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(
                    None,
                    lambda: task.operation(*task.args, **task.kwargs)
                )
            
            result = TaskResult(
                success=True,
                data=data,
                task_type=task.task_type
            )
            self._executed_count += 1
            logger.info(f'✅ [DISPATCH] {task.task_type.value} completed successfully')
            
        except Exception as e:
            result = TaskResult(
                success=False,
                error=str(e),
                task_type=task.task_type
            )
            self._failed_count += 1
            logger.error(f'❌ [DISPATCH] {task.task_type.value} failed: {e}')
        
        # Set result for the awaiter
        if result_future and not result_future.done():
            result_future.set_result(result)
    
    def get_stats(self) -> dict:
        """Get dispatcher statistics."""
        return {
            'running': self._running,
            'queue_size': self._task_queue.qsize(),
            'executed': self._executed_count,
            'failed': self._failed_count,
            'success_rate': (
                self._executed_count / (self._executed_count + self._failed_count)
                if self._executed_count + self._failed_count > 0
                else 0
            )
        }


async def get_telegram_dispatcher() -> TelegramDispatcher:
    """
    Get or create the singleton TelegramDispatcher.
    
    Returns:
        TelegramDispatcher instance
    """
    if TelegramDispatcher._instance is None:
        async with TelegramDispatcher._lock:
            if TelegramDispatcher._instance is None:
                TelegramDispatcher._instance = TelegramDispatcher()
    
    return TelegramDispatcher._instance
