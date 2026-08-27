from pathlib import Path
import subprocess

from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file
from robust_budget_allocation.reproducibility.manifests import build_source_manifest


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_source_manifest_records_git_and_sorted_input_hashes(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "N1 Test")
    _git(root, "config", "user.email", "n1@example.invalid")
    first = root / "b.txt"
    second = root / "a.txt"
    first.write_text("b\n", encoding="utf-8")
    second.write_text("a\n", encoding="utf-8")
    _git(root, "add", "a.txt", "b.txt")
    _git(root, "commit", "-q", "-m", "fixture")

    manifest = build_source_manifest(
        root,
        input_paths=[first, second],
        package_names=(),
    )
    digest = manifest.pop("manifest_sha256")
    assert digest == canonical_json_sha256(manifest)
    assert manifest["git"]["commit_sha"] == _git(root, "rev-parse", "HEAD")
    assert manifest["git"]["tree_sha"] == _git(root, "rev-parse", "HEAD^{tree}")
    assert manifest["inputs"] == [
        {"path": "a.txt", "sha256": sha256_file(second)},
        {"path": "b.txt", "sha256": sha256_file(first)},
    ]
