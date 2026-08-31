# R6-B Formal Experiment Matrix Specification v1

Status: **FROZEN DESIGN FOR INDEPENDENT REVIEW; FORMAL SCIENTIFIC RUNS = 0; R7 NOT STARTED**

The machine authority is `configs/r6_formal_experiment_matrix_v1.json`. It is bound to the independently reviewed R6-A Formal-ready data SHA-256 `3eaf0357d9d586198a8887c59b8e67ebeeb2ab8d7224923db854dca717f236f5`. The expanded deterministic registry is `configs/r6_formal_experiment_matrix_expanded_v1.json`. This specification freezes future R7 work; it does not execute or interpret an optimization result.

## 1. Frozen baseline

The active commodities are Water, Seasonal Influenza Vaccine, and Crackers. Models are M0=Q, M1=Q+F, and M2=Q+F+R. Budget ratios are 0.90, 1.00, and 1.10 of the reviewed R6-A `B_ref`.

Cat1–Cat5 Q survivability is `(0.90, 0.85, 0.80, 0.75, 0.70)`; no-hurricane Q availability is 1. F disruption is `(0.10, 0.30, 0.60, 1.00, 1.00)`; no-hurricane disruption is 0. Reliability effectiveness is `(0, 0.50, 0.80)` and premium ratios are `(0, 0.10, 0.25)cQ`. F pricing is `(phi,psi)=(0.20,0.85)`, with `phi+psi=1.05`. Shortage uses `s_i=beta lambda_i cQ_i`, baseline `beta=4`, and priorities Vaccine/Water/Crackers=`2.5/1.5/1`. Vaccine six-month cold-chain cost is USD 0.50/dose and Crackers retention is 0.90. Combined hurricanes use the maximum constituent category.

These are pre-R7 design values. The Q schedule is a research-design calibration, not a Wang-derived or empirical hurricane-damage estimate. No R6-B setting is chosen from a Formal optimization result.

## 2. E1 main experiment

E1 contains 9 deterministic cases: three models crossed with three budget ratios. It reports economic components, Q/F/R allocations and shares, service/shortage outcomes, the active hurricane scenario, and robust certification fields listed in the machine specification. M0→M1 identifies the incremental role of F; M1→M2 identifies R conditional on F. No ordering or mechanism activation is imposed.

## 3. E2 OFAT sensitivities

All 18 cells use M2 and `B=B_ref`: six families with three registered levels each.

- S1 Vaccine six-month cold-chain cost: `0.25, 0.50, 1.00` USD/dose.
- S2 Crackers retention: `0.80, 0.90, 1.00`.
- S3 F split: `(0.10,0.95), (0.20,0.85), (0.30,0.75)`; every pair sums to 1.05.
- S4 Reliability premium multiplier: `0.50, 1.00, 1.50`.
- S5 Reliability effectiveness: `(0,0.40,0.70), (0,0.50,0.80), (0,0.60,0.90)` with baseline prices unchanged.
- S6 Shortage beta: `2,4,6`, preserving commodity priorities.

Only one family changes in each OFAT cell.

## 4. E3 interactions

Both interactions use M2 and `B=B_ref`. E3-I1 crosses the three Vaccine cold-chain levels with the three F splits (9 cells). E3-I2 crosses `gamma_delta=(0.50,1.00,1.50)` with `gamma_R=(0.50,1.00,1.50)` (9 cells). Its disruption rule is `min(1,gamma_delta*delta_base)`, yielding `(0.05,0.15,0.30,0.50,0.50)`, `(0.10,0.30,0.60,1,1)`, and `(0.15,0.45,0.90,1,1)`. It never changes Q survivability; no-hurricane disruption remains zero.

## 5. E4 OOS evaluation

OOS fixes trained first-stage Q/F/R and re-solves only second-stage x/u. M0, M1, and M2 share evaluation scenarios. Metrics include mean, P50/P90/P95 and worst cost, shortage and shortage probabilities by commodity, F fulfillment, budget feasibility, and severe-tail outcomes.

### E4-A historical LOHO

There are 15 folds, one for each source hurricane h01–h15. Training deletes the held-out single scenario and every combined scenario containing that hurricane. Remaining source probabilities are renormalized without estimation or smoothing. Testing contains every original scenario containing the held-out hurricane and conditionally renormalizes their original source probabilities. No-hurricane remains in training and is not a sixteenth fold. The 15 folds are paired units but are not represented as independent random experiments.

### E4-B synthetic OOS

Seeds are exactly `61001` through `61010`, with 2,000 realizations per seed. A serial `numpy.Generator(PCG64)` is used. For each realization, in order:

1. draw one of all 51 scenarios with replacement using its frozen probability;
2. draw `z~Normal(0,0.1^2)` by rejection until `-0.95<=z<=3.00`;
3. set the shared commodity multiplier `g=1+z`;
4. multiply the selected base scenario's three-component demand vector by the same g;
5. inherit its category, Q availability and disruption without supply noise;
6. save the realization identity.

No clipping or winsorization is permitted. A selected no-hurricane scenario retains zero demand, Q availability 1 and disruption 0 even though the z draw still occurs. The same seed-level dataset and hash are shared by M0/M1/M2. The generator is an R6-B research-design rule, not an empirical hurricane data-generating process.

E4 paired contrasts are `M1-M0` and `M2-M1`. E4-A uses 15 fold-level paired units; E4-B uses 10 seed-level paired units—not 20,000 realizations. Both use a newly preregistered paired percentile bootstrap with 10,000 resamples, seed 62001 and 95% confidence. These settings are R6-B decisions, not inherited defaults.

## 6. E5 algorithms and Memory ablation

E5 uses the 9 E1 cases. Primary algorithms are A0, A1_no_memory and A1_full. EF is only a correctness/reference/certificate anchor. A1_no_memory calls the reviewed A1 with `memory_phase_enabled=False`; A1_full uses `True`. The existing implementation confirms that only the Memory phase/structure changes: Candidate Search, ranking, Full Exact Certification, convergence, formal UB, tolerance, initial pool, ordering, model, data, solver and stopping rules remain unchanged.

Each algorithm/case has one scientific result. Wall-clock timing has three repetitions with identical inputs and state; median is primary and min/max or IQR auxiliary. Repetitions are not scientific seeds. Correctness requires objective, UB, convergence, certificate and model/data/scenario/budget identities to agree within the frozen protocol.

## 7. Statistical and identity rules

E1 receives no pseudo-replication significance test. E2/E3 use effect curves, allocation transitions and relative/boundary interpretation rather than mass p-values. E4-A reports fold-level and aggregate distributions without claiming fold independence. E4-B reports mean±SD and seed-level paired differences plus the registered bootstrap CI.

Every expanded case binds family, model, budget, overrides, scenario/OOS identity, algorithm/Memory state where applicable, this config version, and the R6-A data hash into a canonical SHA-256 experiment identity. Synthetic datasets have seed-specific hashes; identical config/data/seed reproduces the same hash.

## 8. Prohibited execution

R6-B performs configuration expansion, LOHO construction, synthetic-data identity generation and solver-free validation only. It may not call Formal M0/M1/M2, EF, A0, A1, sensitivity, OOS policy evaluation, timing, Gurobi scientific solves, or R7. Formal scientific runs remain zero.
