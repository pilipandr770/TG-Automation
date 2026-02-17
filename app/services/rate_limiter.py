"""
Telegram Rate Limiter — prevents API bans by enforcing per-operation limits.

Uses Redis for distributed counting when available; falls back to in-memory
counters for single-process deployments.
"""

import os
import time
import random
import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Default limits per operation ─────────────────────────────────────────
# Each tuple: (max_count, window_seconds)
DEFAULT_LIMITS: dict[str, list[tuple[int, int]]] = {
    'search': [
        (50, 60),       # 50 per minute (much more lenient for local testing)
        (200, 3600),    # 200 per hour
    ],
    'join_channel': [
        (20, 3600),     # 20 per hour (increased for testing)
        (50, 86400),    # 50 per day
    ],
    'send_message': [
        (5, 60),        # 5 per minute (increased for local testing)
        (50, 3600),     # 50 per hour
    ],
    'read_messages': [
        (50, 60),       # 50 per minute (increased for local testing)
        (500, 3600),    # 500 per hour
    ],
}


class _InMemoryBackend:
    """Fallback rate-limit backend using plain Python dicts."""

    def __init__(self):
        # {operation: [(timestamp, ...),]}
        self._events: dict[str, list[float]] = defaultdict(list)

    async def count_in_window(self, operation: str, window_seconds: int) -> int:
        now = time.time()
        cutoff = now - window_seconds
        events = self._events[operation]
        # Prune old entries
        self._events[operation] = [t for t in events if t > cutoff]
        return len(self._events[operation])

    async def record(self, operation: str) -> None:
        self._events[operation].append(time.time())

    def get_counts(self) -> dict[str, int]:
        """Snapshot of recent event counts (last hour)."""
        now = time.time()
        cutoff = now - 3600
        return {
            op: len([t for t in ts if t > cutoff])
            for op, ts in self._events.items()
        }


class _RedisBackend:
    """Rate-limit backend using Redis sorted sets for distributed counting."""

    def __init__(self, redis_client):
        self._redis = redis_client
        self._prefix = 'tg_rate:'

    async def count_in_window(self, operation: str, window_seconds: int) -> int:
        key = f'{self._prefix}{operation}:{window_seconds}'
        now = time.time()
        cutoff = now - window_seconds
        try:
            # Remove expired entries
            self._redis.zremrangebyscore(key, '-inf', cutoff)
            return self._redis.zcard(key)
        except Exception as e:
            logger.error('Redis count error: %s', e)
            return 0

    async def record(self, operation: str) -> None:
        now = time.time()
        try:
            for _max, window in DEFAULT_LIMITS.get(operation, []):
                key = f'{self._prefix}{operation}:{window}'
                self._redis.zadd(key, {f'{now}': now})
                self._redis.expire(key, window + 60)
        except Exception as e:
            logger.error('Redis record error: %s', e)

    def get_counts(self) -> dict[str, int]:
        counts = {}
        now = time.time()
        try:
            for op in DEFAULT_LIMITS:
                # Use the largest window for a summary count
                windows = DEFAULT_LIMITS[op]
                largest_window = max(w for _, w in windows)
                key = f'{self._prefix}{op}:{largest_window}'
                cutoff = now - largest_window
                self._redis.zremrangebyscore(key, '-inf', cutoff)
                counts[op] = self._redis.zcard(key)
        except Exception as e:
            logger.error('Redis get_counts error: %s', e)
        return counts


class RateLimiter:
    """Enforces Telegram API rate limits to avoid FloodWaitError bans."""

    _instance = None

    def __init__(self):
        self._backend = None
        self._limits = dict(DEFAULT_LIMITS)
        self._init_backend()

    def _init_backend(self) -> None:
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            try:
                import redis
                r = redis.from_url(redis_url, decode_responses=True)
                r.ping()
                self._backend = _RedisBackend(r)
                logger.info('Rate limiter using Redis backend')
                return
            except Exception as e:
                logger.warning('Redis unavailable, falling back to in-memory: %s', e)

        self._backend = _InMemoryBackend()
        logger.info('Rate limiter using in-memory backend')

    # ── public API ───────────────────────────────────────────────────────

    async def acquire(self, operation: str) -> bool:
        """Try to acquire a rate-limit slot for *operation*.

        Returns True if the operation is allowed, False if rate-limited.
        """
        limits = self._limits.get(operation)
        if not limits:
            # Unknown operation — allow by default
            return True

        for max_count, window in limits:
            count = await self._backend.count_in_window(operation, window)
            if count >= max_count:
                logger.warning(
                    'Rate limited: %s (%d/%d in %ds)',
                    operation,
                    count,
                    max_count,
                    window,
                )
                return False

        # All windows OK — record the event
        await self._backend.record(operation)
        return True

    async def handle_flood_wait(self, error) -> None:
        """Handle a Telegram FloodWaitError by sleeping the required time
        plus a small random buffer.
        """
        wait_seconds = getattr(error, 'seconds', 30)
        buffer = random.uniform(5, 15)
        total = wait_seconds + buffer
        logger.warning(
            'FloodWaitError: sleeping %.1f s (required %d + buffer %.1f)',
            total,
            wait_seconds,
            buffer,
        )
        await asyncio.sleep(total)

    def get_stats(self) -> dict[str, int]:
        """Return current usage counts per operation (last hour)."""
        return self._backend.get_counts()


# ── Singleton accessor ───────────────────────────────────────────────────

def get_rate_limiter() -> RateLimiter:
    if RateLimiter._instance is None:
        RateLimiter._instance = RateLimiter()
    return RateLimiter._instance
