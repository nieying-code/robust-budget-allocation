"""Rebuild or check the deterministic R6 Rawls24 data layers; never invokes a solver."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robust_budget_allocation.data.rawls24 import OUTPUT_FILES, build_rawls24_layers, write_rawls24_layers  # noqa: E402
from robust_budget_allocation.io.hashing import sha256_bytes  # noqa: E402


CONFIG = ROOT / "configs/r6_rawls24_data_v1.json"
OUTPUT_DIR = ROOT / "data/r6_rawls24"


def _expected_files() -> dict[str, bytes]:
    product = build_rawls24_layers(CONFIG)
    expected = {OUTPUT_FILES[key]: payload for key, payload in product["payloads"].items()}
    manifest = (json.dumps(product["manifest"], ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    expected["provenance_manifest.json"] = manifest
    hashes = {name: sha256_bytes(payload) for name, payload in expected.items()}
    expected["HASHES.sha256"] = ("\n".join(f"{digest}  {name}" for name, digest in sorted(hashes.items())) + "\n").encode("utf-8")
    return expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify committed outputs without writing")
    args = parser.parse_args()
    if args.check:
        mismatches = []
        for name, expected in _expected_files().items():
            path = OUTPUT_DIR / name
            if not path.exists() or path.read_bytes() != expected:
                mismatches.append(name)
        if mismatches:
            print(json.dumps({"status": "FAIL", "mismatches": mismatches}, indent=2))
            return 1
        product = build_rawls24_layers(CONFIG)
    else:
        product = write_rawls24_layers(CONFIG, OUTPUT_DIR)
    print(json.dumps({
        "status": "PASS",
        "mode": "check" if args.check else "rebuild",
        "canonical_data_sha256": product["manifest"]["canonical_data_sha256"],
        **product["validation"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
