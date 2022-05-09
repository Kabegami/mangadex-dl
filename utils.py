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


def standard_chapter_number(chapter: str) -> str:
    """ return the chapter number with 3 digit to respect cbz convention: 3 -> 003"""
    number = float(chapter)
    is_float = number != number // 1
    if not is_float:
        return chapter.zfill(3)
    int_part = str(int(number // 1)).zfill(3)
    float_part = chapter.split(".")[1]
    return f"{int_part}.{float_part}"


class DomainRateLimiter:
    default_rate = 5
    default_max_token = 5

    def __init__(self, client):
        self.client = client
        self.tokens = defaultdict(lambda: self.default_max_token)
        self.max_tokens = defaultdict(lambda: self.default_max_token)
        self.retry_after = defaultdict(lambda: -1)
        self.updated_at = defaultdict(lambda: time.monotonic())
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


class InvalidChapterSelectionException(Exception):
    def __init__(self, *args, **kwargs):
        super.__init__(*args, **kwargs)

    @classmethod
    def missing_dash(cls, data):
        return cls(f"the input {data} is not a valid range since it doesn't contain a -")

    @classmethod
    def to_many_dashes(cls, data):
        return cls(f"the input {data} is not a valid range since it doesn't contain more than 2 parts")

    @classmethod
    def not_a_number_or_range(cls, data):
        return cls(f"the input {data} is neither a number or a range")


class ChapterSelection:
    """ We select chapters with 2 means :
    specified chapter : where we give specific number of chapter to fetch
    range : in the form of start-end, if one part is missing it consider to have no bound on this side
    for example 12- take all the capter with a number > 12
    """

    def __init__(self):
        self.specified = []
        self.ranges = []
        self.accept_all = False

    def add(self, number):
        self.specified.append(float(number))

    def add_range(self, interval: str):
        if "-" not in interval:
            raise InvalidChapterSelectionException.missing_dash(interval)

        parts = [x for x in interval.split("-") if x]
        if len(parts) == 2:
            start, end = parts
            self.ranges.append((float(start), float(end)))
        elif len(parts) == 1:
            bound = float(parts[0])
            missing_start = interval[0] == "-"
            if missing_start:
                self.ranges.append((-float("inf"), bound))
            else:
                self.ranges.append((bound, float("inf")))
        else:
            raise InvalidChapterSelectionException.to_many_dashes(interval)

    def __contains__(self, item):
        chapter = float(item)
        if chapter in self.specified:
            return True
        for interval in self.ranges:
            start, end = interval
            if start <= chapter <= end:
                return True
        return False

    @classmethod
    def all(cls):
        result = cls()
        result.accept_all = True

    @classmethod
    def parse(cls, selection: str):
        """selection should be a list of chapter number or range (ex : 13-20) separated by comma"""
        result = cls()
        elements = selection.split(",")
        for element in elements:
            if "-" in element:
                result.add_range(element)
            elif element.isnumeric():
                result.add(element)
            else:
                raise InvalidChapterSelectionException.not_a_number_or_range(element)
        return result
