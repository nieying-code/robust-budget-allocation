from pathlib import Path
from threading import Thread

from robust_budget_allocation.io.locking import exclusive_file_lock


def test_lock_acquire_release_and_stale_file(tmp_path: Path) -> None:
    path = tmp_path / "resource.lock"
    path.write_text("stale metadata", encoding="utf-8")
    with exclusive_file_lock(path, timeout_seconds=0.1):
        assert path.exists()
    with exclusive_file_lock(path, timeout_seconds=0.1):
        pass


def test_concurrent_lock_conflict_times_out(tmp_path: Path) -> None:
    path = tmp_path / "resource.lock"
    errors: list[BaseException] = []

    def contend() -> None:
        try:
            with exclusive_file_lock(path, timeout_seconds=0.05):
                pass
        except BaseException as exc:  # record thread outcome for the assertion
            errors.append(exc)

    with exclusive_file_lock(path, timeout_seconds=0.1):
        thread = Thread(target=contend)
        thread.start()
        thread.join(timeout=2)
    assert len(errors) == 1
    assert isinstance(errors[0], TimeoutError)
