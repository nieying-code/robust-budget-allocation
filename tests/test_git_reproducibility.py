from pathlib import Path
import subprocess

import pytest

from robust_budget_allocation.reproducibility.git_state import (
    inspect_git_state,
    require_tracked_files,
    validate_source_state,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "N1 Test")
    _git(root, "config", "user.email", "n1@example.invalid")
    (root / "src").mkdir()
    (root / "src" / "input.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "add", "src/input.py")
    _git(root, "commit", "-q", "-m", "fixture")
    return root


def test_clean_tree_and_commit_tree_manifest(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    state = inspect_git_state(root)
    assert state.commit_sha == _git(root, "rev-parse", "HEAD")
    assert state.tree_sha == _git(root, "rev-parse", "HEAD^{tree}")
    assert not state.tracked_dirty
    assert state.untracked_paths == ()
    report = validate_source_state(
        root,
        required_tracked_paths=[root / "src" / "input.py"],
    )
    assert report["tracked_input_paths"] == ("src/input.py",)


def test_dirty_tracked_input_is_rejected(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    (root / "src" / "input.py").write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="tracked changes"):
        validate_source_state(root)


def test_untracked_and_ignored_scientific_inputs_are_rejected(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    (root / ".gitignore").write_text("src/ignored.py\n", encoding="utf-8")
    _git(root, "add", ".gitignore")
    _git(root, "commit", "-q", "-m", "ignore rule")
    (root / "src" / "ignored.py").write_text("SECRET = 1\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="untracked scientific inputs"):
        validate_source_state(root)


def test_required_input_must_be_tracked_and_inside_repo(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    untracked = root / "plain.txt"
    untracked.write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Git tracked"):
        require_tracked_files(root, [untracked])
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="outside repository"):
        require_tracked_files(root, [outside])
