"""Prepare or run the non-overwriting Rawls24 Layer A N=1000 simulation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from qfr_mechanism_layer_a import prepare, run  # noqa: E402
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file  # noqa: E402
from robust_budget_allocation.simulation.layer_a import load_config, load_rawls24_neutral_fixture  # noqa: E402


CONFIG = ROOT / "configs/qfr_mechanism_layer_a_rawls24_v1.json"
OUTPUT = ROOT / "simulation_results/qfr_mechanism_layer_a_rawls24_n1000"


def _write_comparison(output: Path, new_summary: dict, new_manifest: dict) -> None:
    config = load_config(CONFIG)
    sources = config["comparison_source"]
    loaded = {}
    for name, identity in sources.items():
        path = ROOT / identity["path"]
        if sha256_file(path) != identity["sha256"]:
            raise RuntimeError(f"old 51-scenario comparison {name} hash mismatch")
        loaded[name] = json.loads(path.read_text(encoding="utf-8"))
    old_summary = loaded["summary"]
    old_manifest = loaded["manifest"]
    comparison = {
        "scope": "RAWLS24_VS_RETAINED_51_SCENARIO_LAYER_A_DESCRIPTIVE_COMPARISON",
        "interpretation": "DESCRIPTIVE_ONLY_NO_PARAMETER_TUNING_NO_CAUSAL_ALGORITHM_CLAIM",
        "old_51": {
            "scenario_count": old_manifest["fixture"]["scenario_count"],
            "B_ref": old_manifest["fixture"]["budget"],
            "simulation": old_summary["simulation"],
            "policy_counts": old_summary["policy_counts"],
            "scientific": old_summary["scientific"],
            "computational": old_summary["computational"],
            "source_identity": sources,
        },
        "new_rawls24": {
            "scenario_count": new_manifest["fixture"]["scenario_count"],
            "B_ref": new_manifest["fixture"]["budget"],
            "simulation": new_summary["simulation"],
            "policy_counts": new_summary["policy_counts"],
            "scientific": new_summary["scientific"],
            "computational": new_summary["computational"],
        },
    }
    comparison["comparison_sha256"] = canonical_json_sha256(comparison)
    (output / "comparison_to_old_51.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run"))
    args = parser.parse_args()
    if args.command == "prepare":
        return prepare(CONFIG, OUTPUT, load_rawls24_neutral_fixture)
    return run(CONFIG, OUTPUT, load_rawls24_neutral_fixture, _write_comparison)


if __name__ == "__main__":
    raise SystemExit(main())
