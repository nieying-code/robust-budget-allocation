"""Build the solver-free R6-I Caribbean evidence and canonical data layers."""

from __future__ import annotations

import json

from robust_budget_allocation.data.caribbean import reconstruct


if __name__ == "__main__":
    manifest = reconstruct()
    print(json.dumps({"status": "PASS", "counts": manifest["counts"]}, indent=2))
