import os
from redis import Redis
from rq import Worker, Queue, Connection

listen = ["ocr_tasks"]
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
conn = Redis.from_url(REDIS_URL)

if __name__ == "__main__":
    with Connection(conn):
        worker = Worker(list(map(Queue, listen)))
        worker.work(with_scheduler=True)