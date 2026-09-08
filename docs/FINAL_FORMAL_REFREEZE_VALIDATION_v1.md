# Final Formal re-freeze validation v1

Date: 2026-09-08 Asia/Shanghai.

No scientific optimization, timing benchmark, OOS evaluation, or E1–E5 execution was
performed. `scientific optimization runs = 0`.

Commands and results:

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts/audit_pr27_final_e1_identity.py
.\.venv\Scripts\python.exe scripts/audit_pr27_final_e1_identity.py
```

Result: PASS; 25 identity checks PASS, 0 FAIL, 0 UNKNOWN; deterministic sampler
reconstruction byte-identical; 53 PR artifact hashes verified; 1,000 raw traces read.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_final_formal_refreeze.py tests/test_r6_rawls24_data.py tests/test_n0_design_hashes.py -q
```

Result after preserving historical file hashes: `17 passed, 0 failed`.

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not gurobi" -q
```

Result: `943 passed, 1 skipped, 106 deselected, 0 failed in 371.78s`.

The initially attempted inline status banners on old frozen documents were removed
before commit because they correctly triggered the legacy hash guard. Supersession is
instead recorded in the new centralized registry, preserving all historical hashes.
