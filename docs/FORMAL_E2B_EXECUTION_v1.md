# Formal E2-B Budget Sensitivity — Execution Record

E2-B uses the frozen Final E1 population and changes only the absolute unified
cash budget.  The two new cells are `E2B_B075` and `E2B_B125`, each with the
same 1,000 parameter rows whose SHA-256 is
`ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0`.
The `B100` results are read from frozen Final E1 evidence and are not solved
again.

The exact budgets are produced by binary floating-point multiplication of the
frozen E1 reference value `19137905.85543848`:

- B075: `14353429.391578859`
- B100: `19137905.85543848`
- B125: `23922382.319298096`

All new rows use Rawls24, heterogeneous baseline commodities (`h_V*tau=0.50`,
`a_C=0.90`), M2, beta 4, lambda `(1,1,1)`, gamma_D 1, and
`A1_FINAL_NO_MEMORY_V1` implementation revision
`A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY`.  Each row completes
Candidate Search and Full Exact Certification.  No sample was dropped,
replaced, reordered, or resampled.

The run completed 2,000/2,000 new certified optimizations.  The machine-readable
scientific results, paired triplets, summaries, manifest, and hash inventory are
under `formal_results/e2_final/e2b/`.  Frozen Final E1 and E2-A hash identities
are recorded before execution and checked again during finalization.  E2-A was
neither changed nor rerun.  E2-C and E2-D scientific runs remain zero.

Reproducibility commands use the existing project interpreter:

```powershell
.venv/Scripts/python.exe scripts/run_formal_e2b.py preflight
.venv/Scripts/python.exe scripts/run_formal_e2b.py run-case --case E2B_B075
.venv/Scripts/python.exe scripts/run_formal_e2b.py run-case --case E2B_B125
.venv/Scripts/python.exe scripts/run_formal_e2b.py finalize
.venv/Scripts/python.exe scripts/run_formal_e2b.py verify
```

The first attempted adapter checkpoint was discarded before formal evidence
finalization because a result-serialization key-type defect occurred after
successful solves.  It did not change a scientific input or solver path and no
row from that checkpoint is present in the formal population.  The corrected
adapter was validated on a single certified row before the exact frozen
2,000-row population was executed from `LA-0001` through `LA-1000` in both
cells.
