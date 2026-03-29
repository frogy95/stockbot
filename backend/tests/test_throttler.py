import asyncio
import time

import pytest

from core.clients.throttler import TokenBucketThrottler


@pytest.mark.asyncio
async def test_first_call_immediate():
    throttler = TokenBucketThrottler(interval=1.0)
    start = time.monotonic()
    await throttler.acquire()
    elapsed = time.monotonic() - start
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_second_call_waits():
    throttler = TokenBucketThrottler(interval=1.0)
    await throttler.acquire()
    start = time.monotonic()
    await throttler.acquire()
    elapsed = time.monotonic() - start
    assert 0.9 <= elapsed <= 1.2


@pytest.mark.asyncio
async def test_fast_interval_three_calls():
    throttler = TokenBucketThrottler(interval=0.1)
    start = time.monotonic()
    await throttler.acquire()
    await throttler.acquire()
    await throttler.acquire()
    elapsed = time.monotonic() - start
    assert 0.15 <= elapsed <= 0.35


@pytest.mark.asyncio
async def test_backoff_doubles_interval():
    throttler = TokenBucketThrottler(interval=1.0)
    assert throttler.current_interval == 1.0
    throttler.backoff()
    assert throttler.current_interval == 2.0
    throttler.backoff()
    assert throttler.current_interval == 4.0


@pytest.mark.asyncio
async def test_reset_backoff_restores_interval():
    throttler = TokenBucketThrottler(interval=1.0)
    throttler.backoff()
    throttler.backoff()
    throttler.reset_backoff()
    assert throttler.current_interval == 1.0


@pytest.mark.asyncio
async def test_max_backoff_steps():
    throttler = TokenBucketThrottler(interval=1.0, max_backoff_steps=3)
    throttler.backoff()  # 2.0
    throttler.backoff()  # 4.0
    throttler.backoff()  # 8.0
    throttler.backoff()  # 여전히 8.0 (최대 초과)
    assert throttler.current_interval == 8.0
