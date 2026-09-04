"""Supervised asyncio tasks around the blocking ``JobMachine.run``."""

from __future__ import annotations

import asyncio
import logging
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from app.services.job_records import RESUMABLE_STATES, enum_value
from app.services.progress_hub import ProgressHub

LOGGER = logging.getLogger("gs.api.jobs")


class JobLookupError(KeyError):
    """Job id is unknown to the store/machine."""


class JobMachineProtocol(Protocol):
    def create(self, spec: Any, *, job_id: str | None = None) -> Any: ...

    def run(self, job_id: str) -> Any: ...

    def cancel(self, job_id: str) -> Any: ...

    def retry(self, job_id: str) -> Any: ...

    def get(self, job_id: str) -> Any: ...


class JobStoreProtocol(Protocol):
    def list_by_user(self, user_id: str) -> list[Any]: ...

    def list_resumable(self) -> list[Any]: ...

    def delete(self, job_id: str) -> Any: ...


class JobSupervisor:
    """Registry of in-flight ``machine.run`` tasks.

    * ``dispatch`` starts ``run`` on the default executor (the machine is
      blocking and resume-safe).
    * ``cancel`` calls ``machine.cancel`` so the worker observes
      ``cancel_requested`` between stages.
    * API process restart does not lose jobs: the SQLite store is the source of
      truth; ``resume_interrupted`` re-dispatches every resumable state.
    """

    def __init__(
        self,
        machine: JobMachineProtocol,
        store: JobStoreProtocol,
        hub: ProgressHub,
        *,
        runner: Callable[[str], Any] | None = None,
    ) -> None:
        self.machine = machine
        self.store = store
        self.hub = hub
        self._runner = runner or machine.run
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self.hub.bind_loop(asyncio.get_running_loop())
        await self.resume_interrupted()

    async def resume_interrupted(self) -> None:
        try:
            records = self.store.list_resumable()
        except Exception:  # noqa: BLE001 — boot must not die if the store is empty/corrupt
            LOGGER.exception("Failed to list resumable jobs")
            return
        for record in records:
            state = enum_value(record.state)
            if state not in RESUMABLE_STATES:
                continue
            LOGGER.info("Resuming job %s (state=%s)", record.job_id, state)
            self.dispatch(str(record.job_id))

    def dispatch(self, job_id: str) -> None:
        existing = self._tasks.get(job_id)
        if existing is not None and not existing.done():
            return
        task = asyncio.create_task(self._run(job_id), name=f"pipeline-job-{job_id}")
        self._tasks[job_id] = task
        task.add_done_callback(lambda _t, key=job_id: self._tasks.pop(key, None))

    async def _run(self, job_id: str) -> None:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, self._runner, job_id)
        except asyncio.CancelledError:
            try:
                self.machine.cancel(job_id)
            except Exception:  # noqa: BLE001
                LOGGER.exception("cancel after task cancel failed job_id=%s", job_id)
            raise
        except Exception:  # noqa: BLE001 — isolate worker crashes from the API loop
            LOGGER.exception("JobMachine.run failed job_id=%s", job_id)

    def cancel(self, job_id: str) -> Any:
        record = self.machine.cancel(job_id)
        return record

    def retry(self, job_id: str) -> Any:
        record = self.machine.retry(job_id)
        self.dispatch(job_id)
        return record

    def is_running(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        return task is not None and not task.done()

    def delete(self, job_id: str) -> Any:
        record = self.machine.get(job_id)
        if self.is_running(job_id):
            self.cancel(job_id)
            task = self._tasks.pop(job_id, None)
            if task is not None:
                task.cancel()
        work_dir = Path(str(getattr(record, "work_dir", "") or getattr(record, "work_path", "")))
        deleted = self.store.delete(job_id)
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
        return deleted

    async def shutdown(self) -> None:
        """Drop the registry. In-flight ``run`` calls persist via the store."""
        self._tasks.clear()
