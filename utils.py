import asyncio
import time
import logging
import urllib

from urllib.parse import urlparse
from collections import defaultdict


def safe(fn):
    def helper(*args, **kwargs):
        return fn(*args, **kwargs)

    return helper


def standard_chapter_number(chapter: str) -> str:
    """ return the chapter number with 3 digit to respect cbz convention: 3 -> 003"""
    number = float(chapter)
    is_float = number != number // 1
    if not is_float:
        return chapter.zfill(3)
    int_part = str(int(number // 1)).zfill(3)
    float_part = chapter.split(".")[1]
    return f"{int_part}.{float_part}"


"""
def safe(fn):
    def helper(*args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as ex:
        logging.error(f"{fn.__name__} : {ex}")
        return None
    return helper
"""


class DomainRateLimiter:
    default_rate = 5
    default_max_token = 5

    def __init__(self, client):
        self.client = client
        self.tokens = defaultdict(lambda: self.default_max_token)
        self.max_tokens = defaultdict(lambda: self.default_max_token)
        self.retry_after = defaultdict(lambda: -1)
        self.updated_at = defaultdict(lambda : time.monotonic())
        self.rates = defaultdict(lambda: self.default_rate)

    def register_limit(self, url, headers):
        domain = urlparse(url).netloc

        if self.max_tokens[domain] != self.default_max_token:
            return
        
        limit = headers.get('x-ratelimit-limit')
        if limit is not None:
            limit = int(headers['x-ratelimit-limit'])
            period = 60
            logging.info(f"limiting the domain {domain} to {limit} requests over {period} seconds")
            token_by_seconds = limit / period
            self.max_tokens[domain] = max(token_by_seconds, 1)
            self.rates[domain] = limit / period

    def register_too_many_request(self, url, headers):
        domain = urlparse(url).netloc
        available_at = headers.get('x-ratelimit-retry-after')
        if available_at is not None:
            logging.info(f"Stop sending request to {domain} until {available_at}")
            self.retry_after[domain] = int(available_at)

    async def close(self):
        await self.client.close()

    async def get(self, url, *args, **kwargs):
        logging.debug(f"get : {url}")
        domain = urlparse(url).netloc
        await self.wait_for_token(domain)
        return self.client.get(url, *args, **kwargs)

    async def wait_for_token(self, domain):
        now = int(time.time() // 1)
        while self.tokens[domain] < 1 or now < self.retry_after[domain]:
            await self.add_new_tokens(domain)
            await asyncio.sleep(1)
            now = int(time.time() // 1)
        self.tokens[domain] -= 1

    async def add_new_tokens(self, domain):
        now = time.monotonic()
        elapsed = now - self.updated_at[domain]
        new_tokens = elapsed * self.rates[domain]
        if self.tokens[domain] + new_tokens >= 1:
            self.tokens[domain] = min(self.tokens[domain] + new_tokens, self.max_tokens[domain])
            self.updated_at[domain] = now


class RateLimiter:
    RATE = 5
    MAX_TOKEN = 5

    def __init__(self, client):
        self.client = client
        self.tokens = self.MAX_TOKEN
        self.updated_at = time.monotonic()

    async def close(self):
        await self.client.close()

    async def get(self, *args, **kwargs):
        logging.debug(f"get : {','.join(args)}")
        await self.wait_for_token()
        return self.client.get(*args, **kwargs)

    async def wait_for_token(self):

        while self.tokens <= 1:
            now = time.monotonic()
            await self.add_new_tokens()
            await asyncio.sleep(1)
        self.tokens -= 1

    async def add_new_tokens(self):
        now = time.monotonic()
        elapsed = now - self.updated_at
        new_tokens = elapsed * self.RATE
        if self.tokens + new_tokens >= 1:
            self.tokens = min(self.tokens + new_tokens, self.MAX_TOKEN)
            self.updated_at = now
