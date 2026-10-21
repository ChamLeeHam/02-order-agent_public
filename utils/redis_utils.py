import os

from redis import Redis
from dotenv import load_dotenv

load_dotenv()

def get_redis_client(url: str=None) -> Redis:
    if url is None:
        url = os.getenv("REDIS_URL")

    return Redis.from_url(url, decode_responses=True)