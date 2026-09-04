"""Process execution contract used by every stage runner."""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

LOGGER = logging.getLogger("pipeline.jobs.runner")


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration_s: float


class CommandRunner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_s: float | None = None,
    ) -> CommandResult: ...


class SubprocessRunner:
    """Real subprocess runner for the GPU worker (Linux/WSL2)."""

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_s: float | None = None,
    ) -> CommandResult:
        merged: Mapping[str, str] | None = env
        started = time.monotonic()
        LOGGER.info("event=cmd_start argv=%s", " ".join(argv))
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            env=merged,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        duration = time.monotonic() - started
        LOGGER.info(
            "event=cmd_done returncode=%s duration_s=%.2f argv=%s",
            completed.returncode,
            duration,
            " ".join(argv),
        )
        return CommandResult(
            argv=tuple(argv),
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            duration_s=duration,
        )
