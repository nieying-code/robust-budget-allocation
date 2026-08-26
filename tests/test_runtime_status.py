import json
from pathlib import Path

import pytest

from robust_budget_allocation.runtime.status import (
    MAX_FAILURE_MESSAGE_CHARS,
    compact_failure,
    finalize,
    heartbeat,
    new_status,
    write_status,
)


def test_status_lifecycle_and_atomic_serialization(tmp_path: Path) -> None:
    running = new_status("run-1")
    refreshed = heartbeat(running)
    assert refreshed.state == "running"
    succeeded = finalize(refreshed, "succeeded")
    destination = tmp_path / "status.json"
    write_status(destination, succeeded)
    assert json.loads(destination.read_text(encoding="utf-8"))["state"] == "succeeded"
    with pytest.raises(ValueError, match="terminal"):
        heartbeat(succeeded)


def test_failure_is_normalized_and_bounded() -> None:
    failure = compact_failure(ValueError("x" * (MAX_FAILURE_MESSAGE_CHARS + 20)))
    assert failure["type"] == "ValueError"
    assert len(failure["message"]) == MAX_FAILURE_MESSAGE_CHARS
    failed = finalize(new_status("run-2"), "failed", failure=RuntimeError("boom"))
    assert failed.failure == {"type": "RuntimeError", "message": "boom"}


def test_invalid_status_transitions_fail() -> None:
    with pytest.raises(ValueError, match="nonempty"):
        new_status(" ")
    with pytest.raises(ValueError, match="requires failure"):
        finalize(new_status("run"), "failed")
    with pytest.raises(ValueError, match="invalid terminal"):
        finalize(new_status("run"), "running")
