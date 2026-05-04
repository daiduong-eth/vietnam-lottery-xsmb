"""HTTP client for Minh Ngọc XSMB pages with retry + rate limiting."""

from __future__ import annotations

import asyncio
import logging
from datetime import date

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

BASE_URL = "https://www.minhngoc.net.vn/ket-qua-xo-so/mien-bac"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) xsmb-bot/0.1"

log = logging.getLogger(__name__)


def page_url(d: date) -> str:
    return f"{BASE_URL}/{d:%d-%m-%Y}.html"


class Fetcher:
    """Async HTTP fetcher with semaphore-based rate limiting."""

    def __init__(
        self, *, concurrency: int = 4, min_interval: float = 0.5, timeout: float = 20.0
    ) -> None:
        self._sem = asyncio.Semaphore(concurrency)
        self._min_interval = min_interval
        self._client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "vi,en;q=0.8"},
            timeout=timeout,
            follow_redirects=True,
            http2=False,
        )
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> Fetcher:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    async def fetch(self, d: date) -> str:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1, min=2, max=20),
            retry=retry_if_exception_type((httpx.HTTPError,)),
            reraise=True,
        ):
            with attempt:
                async with self._sem:
                    await self._throttle()
                    response = await self._client.get(page_url(d))
                    response.raise_for_status()
                    return response.text
        raise RuntimeError("unreachable")

    async def _throttle(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait = self._min_interval - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = asyncio.get_event_loop().time()
