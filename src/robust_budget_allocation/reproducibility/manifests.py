"""Machine-readable manifests without model- or scenario-specific fields."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path
import platform
import sys
from typing import Iterable

from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file

from .git_state import inspect_git_state


def package_versions(names: Iterable[str]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in names:
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = None
    return result


def build_source_manifest(
    project_root: Path,
    *,
    input_paths: Iterable[Path] = (),
    package_names: Iterable[str] = ("Pyomo", "gurobipy", "numpy", "filelock"),
) -> dict[str, object]:
    root = project_root.resolve()
    state = inspect_git_state(root)
    inputs: list[dict[str, str]] = []
    for path in input_paths:
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"manifest input is outside repository: {resolved}") from exc
        inputs.append({"path": relative, "sha256": sha256_file(resolved)})
    payload: dict[str, object] = {
        "schema_version": 1,
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "platform": platform.platform(),
        "packages": package_versions(package_names),
        "git": state.to_dict(),
        "inputs": sorted(inputs, key=lambda value: value["path"]),
    }
    payload["manifest_sha256"] = canonical_json_sha256(payload)
    return payload
