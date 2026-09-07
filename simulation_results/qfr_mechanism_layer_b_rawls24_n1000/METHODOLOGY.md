# Rawls24 Layer B commodity heterogeneity simulation

This exploratory Layer B run pairs draw `n` with the identically numbered draw in the
certified Rawls24 homogeneous Layer A run. The stored `samples.csv` is byte-identical
to the Layer A table; it is not resampled or modified.

Only the existing commodity-specific baseline is restored:

- Water: monthly holding cost `h=0`, retention `a=1`.
- Seasonal Influenza Vaccine: monthly cold-chain cost `h=0.0833333333333333`,
  six-month horizon `tau=6`, and retention `a=1` (six-month cost = 0.5 per dose).
- Crackers: monthly holding cost `h=0` and retention `a=0.9`.

The values are read from `configs/r6c_formal_ready_data_v2.json` and independently
checked against the baseline in `configs/r6c_formal_experiment_matrix_v2.json`.
They are not recalibrated. The existing reference-budget formula is applied
mechanically to the same Rawls24 reference demand:

`B_ref = sum_i ((cQ_i + h_i * tau) * Dref_i / a_i)`.

All Q/F/R parameter values, the Rawls24 scenarios and reference weights, model M2,
production A1_full, beta=4, gamma_D=1, and the numerical validation path are unchanged.
This is an exploratory mechanism simulation, not Formal E1-E5 and not parameter tuning.

Reproduction commands:

```powershell
.\.venv\Scripts\python.exe scripts\qfr_mechanism_layer_b_rawls24.py prepare
.\.venv\Scripts\python.exe scripts\qfr_mechanism_layer_b_rawls24.py run
```

The `prepare` command is only used before the output directory exists. The committed
prepared sample identity is an execution prerequisite; a completed directory is not
overwritten by either command.
