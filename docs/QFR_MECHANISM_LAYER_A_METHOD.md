# Q-F-R Mechanism Simulation — Layer A

This exploratory simulation maps broad admissible mechanism parameters to the
optimal policy returned by the unchanged production `M2` model and unchanged
production `A1_full` algorithm. It is not parameter calibration, a Formal
E1–E5 execution, or a probability model for real conditions.

The deterministic sampler uses NumPy PCG64 with seed `20260903`. Every scalar
marginal is an exact 1,000-stratum Latin hypercube over its configured uniform
range. Monotone Q and F curves are formed by deterministic randomized matching
of adjacent LHS columns: each lower-severity column retains all its original
LHS values while every matched next-category value is no greater. The same
matching construction, with reversed inequality, enforces the minimum gaps for
`eta_2` and the R2 premium. This avoids rejection sampling and preserves every
one-dimensional LHS marginal.

Layer A uses the existing 51-scenario R6-C Formal-ready demand and scenario
schema as an immutable source. Budget is fixed at `1.00 × B_ref =
7,975,014.2749022` from that source, shortage beta is 4, demand scale gamma_D
is 1, and the neutral commodity controls set all
storage costs `h=0` and retention factors `a=1`. A draw changes only Q
availability, baseline F availability, R1/R2 mitigation effectiveness, F
reservation/exercise price ratios, and R1/R2 premium ratios. Baseline F
availability is represented by `delta=1-rho_F` with `eta_0=0`; the production
availability expression `1-(1-eta_r)delta` is unchanged.

Policy classification uses absolute tolerance `1e-7`. P1 is Q-only; P2 is
Q+F with only R0; P3a/P3b are Q+F with R1/R2 respectively (highest active paid
level governs); P4 has active F and approximately zero Q; P5 retains all other
corner structures. Raw production A1 results are stored in deterministic gzip
JSONL shards without deleting trace, memory, candidate, oracle, certificate,
or seal fields.

Reproduction commands:

```text
.venv\Scripts\python.exe scripts\qfr_mechanism_layer_a.py prepare
.venv\Scripts\python.exe scripts\qfr_mechanism_layer_a.py run
```

No figures are produced by Layer A.
