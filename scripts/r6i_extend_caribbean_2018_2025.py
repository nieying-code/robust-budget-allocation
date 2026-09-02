"""Build the solver-free R6-I Caribbean historical extension and combined layer."""

from __future__ import annotations

import json

from robust_budget_allocation.data.caribbean_extension import build_extension


if __name__ == "__main__":
    manifest = build_extension()
    print(json.dumps({
        "status": "PASS",
        "extension_counts": manifest["extension_counts"],
        "combined_counts": manifest["combined_counts"],
    }, indent=2))
