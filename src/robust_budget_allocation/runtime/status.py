"""Small generic status and heartbeat records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from robust_budget_allocation.io.atomic import atomic_write_json


MAX_FAILURE_MESSAGE_CHARS = 1_000
TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_failure(value: BaseException | Mapping[str, Any] | str) -> dict[str, str]:
    if isinstance(value, BaseException):
        failure_type = type(value).__name__
        message = str(value)
    elif isinstance(value, Mapping):
        failure_type = str(value.get("type") or value.get("error_type") or "Error")
        message = str(value.get("message") or value.get("error") or "")
    else:
        failure_type = "Error"
        message = str(value)
    return {
        "type": failure_type[:200],
        "message": message[:MAX_FAILURE_MESSAGE_CHARS],
    }


@dataclass(frozen=True)
class RunStatus:
    run_id: str
    state: str
    created_at: str
    updated_at: str
    heartbeat_at: str
    failure: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_status(run_id: str) -> RunStatus:
    if not run_id.strip():
        raise ValueError("run_id must be nonempty")
    now = utc_now()
    return RunStatus(run_id=run_id, state="running", created_at=now, updated_at=now, heartbeat_at=now)


def heartbeat(status: RunStatus) -> RunStatus:
    if status.state in TERMINAL_STATES:
        raise ValueError("terminal status cannot receive a heartbeat")
    now = utc_now()
    return RunStatus(**{**status.to_dict(), "updated_at": now, "heartbeat_at": now})


def finalize(
    status: RunStatus,
    state: str,
    *,
    failure: BaseException | Mapping[str, Any] | str | None = None,
) -> RunStatus:
    if status.state in TERMINAL_STATES:
        raise ValueError("status is already terminal")
    if state not in TERMINAL_STATES:
        raise ValueError(f"invalid terminal state: {state}")
    if state == "failed" and failure is None:
        raise ValueError("failed status requires failure details")
    now = utc_now()
    return RunStatus(
        run_id=status.run_id,
        state=state,
        created_at=status.created_at,
        updated_at=now,
        heartbeat_at=status.heartbeat_at,
        failure=compact_failure(failure) if failure is not None else None,
    )


def write_status(path: Path, status: RunStatus) -> None:
    atomic_write_json(path, status.to_dict())
