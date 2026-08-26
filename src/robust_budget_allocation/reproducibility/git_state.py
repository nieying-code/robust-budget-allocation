"""Generic Git source-state inspection and execution gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import subprocess
from typing import Iterable


@dataclass(frozen=True)
class GitState:
    commit_sha: str
    tree_sha: str
    tracked_dirty: bool
    untracked_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _git(root: Path, *arguments: str, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=text,
    )


def inspect_git_state(root: Path) -> GitState:
    root = root.resolve()
    commit = _git(root, "rev-parse", "HEAD").stdout.strip()
    tree = _git(root, "rev-parse", "HEAD^{tree}").stdout.strip()
    tracked = _git(root, "status", "--porcelain", "--untracked-files=no").stdout
    untracked_raw = _git(
        root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        text=False,
    ).stdout
    untracked = tuple(
        value.decode("utf-8", errors="replace")
        for value in untracked_raw.split(b"\0")
        if value
    )
    return GitState(commit, tree, bool(tracked.strip()), untracked)


def _untracked_under_roots(root: Path, scientific_roots: Iterable[str]) -> tuple[str, ...]:
    roots = tuple(str(value).strip("/") for value in scientific_roots)
    if not roots:
        return ()
    raw = _git(root, "ls-files", "--others", "-z", "--", *roots, text=False).stdout
    return tuple(
        value.decode("utf-8", errors="replace")
        for value in raw.split(b"\0")
        if value
        and "__pycache__/" not in value.decode("utf-8", errors="replace")
        and not value.decode("utf-8", errors="replace").endswith((".pyc", ".pyo"))
    )


def require_tracked_files(root: Path, paths: Iterable[Path]) -> tuple[str, ...]:
    resolved_root = root.resolve()
    relative: list[str] = []
    for path in paths:
        resolved = path.resolve()
        try:
            name = resolved.relative_to(resolved_root).as_posix()
        except ValueError as exc:
            raise RuntimeError(f"execution input is outside repository: {resolved}") from exc
        if not resolved.is_file():
            raise RuntimeError(f"execution input is missing: {name}")
        relative.append(name)
    if not relative:
        return ()
    completed = subprocess.run(
        ["git", "-C", str(resolved_root), "ls-files", "--error-unmatch", "--", *relative],
        check=False,
        capture_output=True,
        text=True,
    )
    tracked = set(completed.stdout.splitlines())
    missing = [value for value in relative if value not in tracked]
    if completed.returncode or missing:
        raise RuntimeError("execution inputs must be Git tracked: " + ", ".join(missing or relative))
    return tuple(relative)


def validate_source_state(
    root: Path,
    *,
    required_tracked_paths: Iterable[Path] = (),
    scientific_roots: Iterable[str] = ("src", "configs", "scripts"),
) -> dict[str, object]:
    state = inspect_git_state(root)
    if state.tracked_dirty:
        raise RuntimeError("execution requires no staged or unstaged tracked changes")
    untracked_scientific = _untracked_under_roots(root.resolve(), scientific_roots)
    if untracked_scientific:
        raise RuntimeError(
            "execution found untracked scientific inputs: " + ", ".join(untracked_scientific[:20])
        )
    tracked_inputs = require_tracked_files(root, required_tracked_paths)
    result = state.to_dict()
    result["tracked_input_paths"] = tracked_inputs
    result["untracked_scientific_paths"] = ()
    return result
