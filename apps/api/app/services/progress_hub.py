"""Thread-safe fan-out of pipeline ProgressEvent to WebSocket subscribers."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator

from app.schemas.jobs import ProgressPayload


class ProgressHub:
    """One latest snapshot per job plus per-connection queues.

    ``JobMachine.run`` is blocking and executes in a worker thread; ``publish``
    is therefore safe to call from any thread.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: dict[str, ProgressPayload] = {}
        self._subscribers: dict[str, list[asyncio.Queue[ProgressPayload]]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def latest(self, job_id: str) -> ProgressPayload | None:
        with self._lock:
            payload = self._latest.get(job_id)
        return payload

    def publish(self, job_id: str, payload: ProgressPayload) -> None:
        with self._lock:
            self._latest[job_id] = payload
            queues = list(self._subscribers.get(job_id, ()))
        loop = self._loop
        for queue in queues:
            if loop is None:
                continue
            loop.call_soon_threadsafe(self._enqueue, queue, payload)

    def _enqueue(self, queue: asyncio.Queue[ProgressPayload], payload: ProgressPayload) -> None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                return

    def _add(self, job_id: str, queue: asyncio.Queue[ProgressPayload]) -> None:
        with self._lock:
            self._subscribers.setdefault(job_id, []).append(queue)

    def _remove(self, job_id: str, queue: asyncio.Queue[ProgressPayload]) -> None:
        with self._lock:
            holders = self._subscribers.get(job_id)
            if not holders:
                return
            if queue in holders:
                holders.remove(queue)
            if not holders:
                self._subscribers.pop(job_id, None)

    async def subscribe(self, job_id: str) -> AsyncIterator[ProgressPayload]:
        queue: asyncio.Queue[ProgressPayload] = asyncio.Queue(maxsize=64)
        self._add(job_id, queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._remove(job_id, queue)
