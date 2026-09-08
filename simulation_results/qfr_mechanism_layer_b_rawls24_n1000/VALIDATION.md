# Validation record

Execution date: 2026-09-07 (Asia/Shanghai).

Targeted Layer A/Layer B/Rawls24/A1/model regression command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_qfr_mechanism_layer_b_rawls24.py tests/test_qfr_mechanism_layer_a_rawls24.py tests/test_qfr_mechanism_layer_a_t1.py tests/test_qfr_mechanism_layer_a.py tests/test_r4_qfr_a1.py tests/test_n5_a1.py tests/test_n4_correctness.py tests/test_r3_qfr_correctness_unit.py tests/test_m0_model.py tests/test_r6_rawls24_data.py -q
```

Result: `227 passed, 0 failed`.

Full repository regression command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Result: `1082 passed, 1 skipped, 0 failed in 806.79s`.

The completed-output test verifies 1000 scientific rows, 1000 paired rows, all
SUCCESS/PASS certificates, 24 scenario audit rows, the exact mixed-policy counts,
h09 worst count, and every entry in `HASHES.sha256`.
