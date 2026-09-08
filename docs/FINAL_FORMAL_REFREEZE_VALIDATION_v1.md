# Final Formal re-freeze validation v1

Date: 2026-09-08 Asia/Shanghai.

No scientific optimization, timing benchmark, OOS policy evaluation, or E1–E5
execution was performed. `scientific optimization runs = 0`. Synthetic input
generation below is solver-free and exists only to seal deterministic identities.

## Static PR #27 identity audit

```powershell
.\.venv\Scripts\python.exe scripts/audit_pr27_final_e1_identity.py --output docs/evidence/PR27_FINAL_E1_IDENTITY_AUDIT_v1.json
```

Result: PASS; 25 identity checks PASS, 0 FAIL, 0 UNKNOWN; deterministic sample
reconstruction byte-identical; 53 PR artifact hashes verified; 1,000 raw traces read.
PR #27 was read as committed git blobs and was not checked out or modified.

## Machine-identity deterministic rebuild

```powershell
.\.venv\Scripts\python.exe scripts/freeze_final_formal_machine_identities.py
```

Result: PASS. The frozen sample hash was verified before selection. S_200, nested
S_100, E3-B parameter representatives, ten E4-B 2,000-scenario input-table hashes,
30 E5-B nested-pool identities/budgets, and 30 E5-C nested-item identities were
reconstructed byte-for-byte from their recorded sources and seeds.

## Compilation and targeted solver-free tests

```powershell
.\.venv\Scripts\python.exe -m py_compile src/robust_budget_allocation/formal/final_design.py scripts/freeze_final_formal_machine_identities.py scripts/audit_pr27_final_e1_identity.py
.\.venv\Scripts\python.exe -m pytest tests/test_final_formal_machine_definition.py tests/test_final_formal_refreeze.py tests/test_r6_rawls24_data.py tests/test_n0_design_hashes.py -q -k "not final_design_hash_manifest"
```

Result: `23 passed, 1 deselected, 0 failed`. The one deselected test is the final
hash-manifest guard, run separately after the manifest itself is updated.

## Full solver-free regression

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not gurobi" -q
```

Final result after the hash manifest was sealed:
`950 passed, 1 skipped, 106 deselected, 0 failed in 384.15s`.

## Frozen status

- Formal scientific machine-definition open decisions: 0.
- PR #27 engineering promotion: pending independent approval (non-scientific gate).
- Final A1: `A1_FINAL_NO_MEMORY_V1`; no Memory metric is admissible in E5.
- PR #27 reuse candidate: YES, scientific outputs only; runtime/Memory evidence excluded.

## E5-C 100-scenario demand-generator gap closure

The existing E5-C helper was extended, without solver imports, to generate the shared
100-scenario master structure after the nine item draws. It records uniform Rawls24
template IDs, inherited categories, one scenario-common shock, complete nine-item
demand vectors, I3/I6/I9 demand-matrix hashes, and size-specific benchmark budgets.

```powershell
.\.venv\Scripts\python.exe scripts/freeze_final_formal_machine_identities.py
.\.venv\Scripts\python.exe -m pytest tests/test_final_formal_machine_definition.py tests/test_final_formal_refreeze.py -q -k "not final_design_hash_manifest"
.\.venv\Scripts\python.exe -m pytest -m "not gurobi" -q -k "not final_design_hash_manifest"
```

Pre-seal results: deterministic rebuild PASS; targeted `19 passed, 1 deselected`;
full solver-free `953 passed, 1 skipped, 107 deselected, 0 failed in 405.09s`.
The sole extra deselection is the hash guard, which is executed after the updated
manifest is sealed. Scientific optimization runs remained zero.

After sealing the manifest, the targeted suite passed `20/20`, and the complete
unfiltered solver-free command passed:
`954 passed, 1 skipped, 106 deselected, 0 failed in 385.58s`.
