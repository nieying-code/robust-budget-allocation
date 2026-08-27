from pathlib import Path, PurePosixPath, PureWindowsPath
import re

import pytest

from robust_budget_allocation.io.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "N1_MIGRATION_HASHES.sha256"
FROZEN_N1_MIGRATION_PATHS = frozenset(
    {
        ".github/workflows/ci.yml",
        "README.md",
        "docs/LEGACY_MIGRATION_MANIFEST_v1.md",
        "docs/N1_MIGRATION_REPORT.md",
        "docs/STATUS.md",
        "pyproject.toml",
        "requirements.txt",
        "src/robust_budget_allocation/environment.py",
        "src/robust_budget_allocation/io/__init__.py",
        "src/robust_budget_allocation/io/atomic.py",
        "src/robust_budget_allocation/io/hashing.py",
        "src/robust_budget_allocation/io/locking.py",
        "src/robust_budget_allocation/reproducibility/__init__.py",
        "src/robust_budget_allocation/reproducibility/git_state.py",
        "src/robust_budget_allocation/reproducibility/manifests.py",
        "src/robust_budget_allocation/runtime/__init__.py",
        "src/robust_budget_allocation/runtime/environment.py",
        "src/robust_budget_allocation/runtime/solver.py",
        "src/robust_budget_allocation/runtime/status.py",
        "src/robust_budget_allocation/statistics/__init__.py",
        "src/robust_budget_allocation/statistics/bootstrap.py",
        "src/robust_budget_allocation/statistics/cvar.py",
        "src/robust_budget_allocation/statistics/multiple_testing.py",
        "tests/test_atomic_hashing.py",
        "tests/test_git_reproducibility.py",
        "tests/test_locking.py",
        "tests/test_manifests.py",
        "tests/test_n1_migration_hashes.py",
        "tests/test_runtime_environment.py",
        "tests/test_runtime_status.py",
        "tests/test_solver_runtime.py",
        "tests/test_statistics_helpers.py",
    }
)
ENTRY_PATTERN = re.compile(r"^([0-9a-f]{64})  (.+)$")


def _parse_manifest(path: Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = ENTRY_PATTERN.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid hash entry at line {line_number}")
        digest, relative = match.groups()
        posix = PurePosixPath(relative)
        windows = PureWindowsPath(relative)
        if (
            posix.is_absolute()
            or windows.is_absolute()
            or ".." in posix.parts
            or ".." in windows.parts
        ):
            raise ValueError(f"unsafe hash path: {relative}")
        entries.append((digest, relative))
    paths = [relative for _, relative in entries]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate hash path")
    return entries


def test_n1_migration_hash_manifest() -> None:
    entries = _parse_manifest(MANIFEST)
    paths = {relative for _, relative in entries}
    assert paths == FROZEN_N1_MIGRATION_PATHS
    assert "docs/N1_MIGRATION_HASHES.sha256" not in paths
    for expected, relative in entries:
        path = ROOT / relative
        assert path.is_file() and not path.is_symlink(), relative
        assert sha256_file(path) == expected, relative


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "/absolute.py",
        "C:/absolute.py",
        "../escape.py",
        "src/../escape.py",
        "..\\escape.py",
    ],
)
def test_hash_manifest_rejects_absolute_and_parent_paths(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    manifest = tmp_path / "hashes.sha256"
    manifest.write_text(f"{'0' * 64}  {unsafe_path}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe hash path"):
        _parse_manifest(manifest)


def test_hash_manifest_rejects_duplicate_paths(tmp_path: Path) -> None:
    manifest = tmp_path / "hashes.sha256"
    entry = f"{'0' * 64}  src/example.py\n"
    manifest.write_text(entry + entry, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate hash path"):
        _parse_manifest(manifest)
