"""
RQ Worker entry point (Process 3).
Handles on-demand batch tasks queued from Flask admin.
"""
import os
import logging
from redis import Redis
from rq import Worker, Queue

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
conn = Redis.from_url(redis_url)

if __name__ == '__main__':
    queues = [Queue('telegram-tasks', connection=conn)]
    worker = Worker(queues, connection=conn)
    worker.work()
