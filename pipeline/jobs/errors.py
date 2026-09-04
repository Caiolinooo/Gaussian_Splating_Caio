"""Job-layer errors."""

from __future__ import annotations


class JobError(Exception):
    def __init__(self, message: str, *, user_message: str, code: str) -> None:
        super().__init__(message)
        self.user_message = user_message
        self.code = code


class JobInterrupted(BaseException):
    """Simulated worker kill / cooperative abort — not an ``Exception``.

    The store keeps the current stage as ``running`` so a new worker can resume.
    """


class InvalidTransition(JobError):
    def __init__(self, current: str, dest: str) -> None:
        super().__init__(
            f"invalid transition {current} -> {dest}",
            user_message="O job está num estado que não permite essa operação.",
            code="INVALID_TRANSITION",
        )


class JobNotFound(JobError):
    def __init__(self, job_id: str) -> None:
        super().__init__(
            f"job not found: {job_id}",
            user_message="Job não encontrado.",
            code="NOT_FOUND",
        )


class JobCancelled(JobError):
    def __init__(self, job_id: str) -> None:
        super().__init__(
            f"job cancelled: {job_id}",
            user_message="O job foi cancelado.",
            code="CANCELLED",
        )
