# Final Formal Scientific Design v1

Status: **FROZEN SCIENTIFIC DESIGN / EXECUTION NOT AUTHORIZED / SCIENTIFIC OPTIMIZATION RUNS = 0**

This document is the sole active authority for the final E1–E5 design. It supersedes
the historical 15/51-scenario, nine-case E1, Memory-guided A1, A1 ablation, and
12/24-item scalability protocols listed in `FINAL_FORMAL_SUPERSEDED_REGISTRY_v1.md`.
The machine-readable companion is `configs/final_formal_scientific_design_v1.json`.
No rule below was selected from an optimization outcome.

## 1. Common scientific identity

- Empirical data: Rawls24, exactly `h01` through `h24` in that order, each a real
  single-hurricane scenario. Combined and no-hurricane scenarios are excluded.
- Commodities, in order: Water, Seasonal Influenza Vaccine, Crackers.
- Archetypes: standard-storable, preservation-sensitive, storage-loss-sensitive.
- Full scientific model: M2 = Q + F + R. The mathematical model, unified cash
  budget, recourse, objective/T-COST, and R-only-protects-F rule remain unchanged.
- Default E1–E4 solver: final exact A1 defined in section 2.
- E1 baseline: beta=4, lambda=(1,1,1), gamma_D=1, Water `(h,a)=(0,1)`, Vaccine
  `(h*tau,a)=(0.50,1)`, Crackers `(h,a)=(0,0.90)`.
- Absolute E1 budget: `B_ref^E1 = 19,137,905.85543848`.
- Except for E2-B and explicitly stated computational normalization, changes to
  h, a, beta, or lambda never trigger budget recomputation. This separates the
  mechanism intervention from a budget intervention.

## 2. Final A1 identity: no Memory

`A1_FINAL_NO_MEMORY_V1 = Candidate Search + Full Exact Certification + numerically
robust exact oracle`.

Memory Inspection, memory hits, memory ablation, memory contribution, `A1_full`,
and `A1_no_memory` as an ablation label are not part of the final scientific
algorithm. Historical implementations and fields may remain for traceability but
must be labeled `HISTORICAL_ONLY` and cannot support paper claims or E5 metrics.

The current production entry point may be reused only with Memory disabled. Candidate
ranking/search, full exact certification, stopping and convergence, solver policy,
and exactness rules remain unchanged. Numerical feasibility validation uses the
audited scale-aware rule `abs_violation <= 1e-7 + 1e-12*family_scale`; this rule
validates a solver representation and does not relax scientific feasibility or the
global convergence tolerance. Objective/bound convergence remains
`1e-7 + 1e-9*max(1,abs(a),abs(b))`. Solver policy remains `gurobi_direct`, one
thread, no fallback, MIPGap/MIPGapAbs=0, and feasibility/optimality/integrality
tolerances `1e-9`.

## 3. E1 — Parameter-Space Main Experiment

E1 uses Rawls24, all three heterogeneous commodities, M2, final no-memory A1,
`B=B_ref^E1`, beta=4, lambda=(1,1,1), and gamma_D=1. It reuses—without
regeneration—the 1,000-row deterministic constrained LHS table with seed `20260903`
and SHA-256 `ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0`.

Parameter bounds are:

- rho_Q Cat1–Cat5: `[.80,.98]`, `[.70,.94]`, `[.60,.88]`, `[.50,.82]`,
  `[.40,.75]`, nonincreasing by severity.
- rho_F Cat1–Cat5: `[.70,.98]`, `[.60,.95]`, `[.50,.92]`, `[.40,.88]`,
  `[.30,.85]`, nonincreasing by severity. No rho_F/rho_Q cross-order is imposed.
- eta_1 `[.05,.50]`, eta_2 `[.40,.90]`, with eta_2>eta_1 and gap>=.05.
- phi `[0,.50]`, psi `[.50,1.50]`; their sum is not constrained.
- R1/cQ `[.02,.30]`, R2/cQ `[.15,.60]`, with R2>R1 and gap>=.05.

Aggregate labels use the frozen explicit tolerance `1e-7`: P1 Q-only; P2 Q+F+R0;
P3a Q+F+R1; P3b Q+F+R2; P4 F-dominant/Q approximately zero; P5 other/corner.
Exact floating-point zero is prohibited. E1 must also retain item-level Q/F activity,
NONE/R0/R1/R2, cross-commodity portfolios, same-item coexistence, cross-item
specialization, and parameter-region mappings. Policy shares describe sampled
parameter-space coverage, never real-world probabilities.

## 4. E2 — Managerial Sensitivity Analysis

Use the same 1,000 E1 draws and paired comparisons wherever possible. The E1
baseline is reused rather than rerun.

### E2-A Commodity heterogeneity (OFAT)

Baseline `(h_V*tau,a_C)=(.50,.90)`. New cells are `(0,.90)`, `(1,.90)`,
`(.50,1)`, and `(.50,.80)`: 4,000 new optimizations. All use the fixed absolute
`B_ref^E1`; no budget recomputation is permitted.

### E2-B Budget

Use `.75`, `1.00`, and `1.25` times `B_ref^E1`; baseline reuses E1, giving 2,000
new optimizations. Report allocation, shortage, T-COST, policy transitions, and
marginal budget flows by commodity and instrument.

### E2-C Reliability boundary

Default new optimizations: zero. Analyze E1 rows conditional on item-level F_i>tol.
The descriptive indices are `A_R1=eta_1/(c_R1/cQ)` and
`A_R2=(eta_2-eta_1)/((c_R2-c_R1)/cQ)`. They are descriptive, not causal thresholds.
Any future targeted diagnostic requires explicit authorization.

### E2-D Shortage valuation and priority

E2-D1 beta=`2,4,6`; beta=4 reuses E1, giving 2,000 new optimizations. E2-D2 keeps
beta=4 and tests, in `(Water,Vaccine,Crackers)` order, `(1.5,1,1)`, `(1,1.5,1)`,
and `(1,1,1.5)`: 3,000 new optimizations. These are symmetric managerial preference
perturbations, not empirical or intrinsic rankings. Total planned E2 new runs are
11,000, excluding any separately approved E2-C diagnostic.

## 5. E3 — Targeted Interaction Experiment

Select one shared `N_E3=200` subset from the frozen E1 table using deterministic,
outcome-independent maximin/space-filling. Policy, objective, runtime, R activation,
and candidate hits are forbidden selection inputs. Exact normalization, initialization,
distance, and tie-breaking remain an execution-blocking open decision; no row IDs are
claimed frozen in this version.

### E3-A Storage burden x F economics

Cross Vaccine `h_V*tau={0,.50,1.00}` with `m_F={.8,1,1.2}` applied jointly to
the reference `(phi,psi)=(.20,.85)`. The three F pairs are `(.16,.68)`,
`(.20,.85)`, and `(.24,1.02)`. Maximum 1,800 optimizations; duplicate baseline
cells may be reused.

### E3-B F supply risk x reliability economics

For every frozen E1 row, compute `S_F=(1/5)*sum_k(1-rho_F,k)`. Select actual full
rho_F curves nearest Q25/Q50/Q75 as Low/Medium/High supply risk without using outcomes.

Reliability economics is restricted to the E1 F-active subset. Compute A_R1 and A_R2
as above, z-score each, and set `A_R=.5*(Z(A_R1)+Z(A_R2))`; actual rows nearest
Q25/Q50/Q75 define Unfavorable/Reference/Favorable. R label, objective, and runtime
cannot enter selection. The meaning of row-level F-active membership, z-score
population, and deterministic tie/de-duplication are not uniquely specified, so this
cell is `OPEN_DECISION_E3B_RELIABILITY_SELECTION` and is not fully machine-defined.
Maximum after resolution: 1,800 optimizations. E3 theoretical maximum: 3,600.

## 6. E4 — Out-of-Sample Robustness

### E4-A Historical LOHO

Use the same eventual deterministic outcome-independent 200-row subset. For each of
24 hurricanes, optimize on the other 23 and evaluate the held-out event: 4,800
training optimizations. Every fold uses absolute `B_ref^E1`; leave-one-out budget
recalculation is prohibited. Preserve held-out T-COST, shortage, service level,
regret, policy change, and full24-versus-LOHO policy comparison.

### E4-B Synthetic OOS

Select 100 policies from the 200 representatives by deterministic outcome-independent
space filling. Evaluate 2,000 synthetic scenarios per policy under 10 fixed seeds,
primarily by second-stage evaluation rather than first-stage reoptimization.

No current active source defines a complete Rawls24 scientific OOS generator covering
demand, category, Q/F availability, cross-commodity dependence, no-hurricane handling,
and seed policy. The old 51-scenario generator is historical and cannot substitute.
Therefore `OPEN_DECISION_E4B_GENERATOR` remains; E4-B is not fully frozen and cannot run.

## 7. E5 — Algorithmic Performance and Scalability

Compare only A0 with final no-memory A1. Use three timing repetitions per
algorithm-instance and the median as instance runtime. Repetitions are not independent
statistical samples. Speedup is median(A0)/median(A1); report median, IQR, P90, and
geometric mean speedup. Retain objective, absolute objective difference, runtime,
iterations, scenario evaluations, candidate hits, full exact certification calls,
convergence, timeout, and failure. Memory metrics are prohibited. Instances cannot be
redrawn after timeout or failure.

### E5-A Rawls24 real-case benchmark

Use a deterministic outcome-independent 200-row E1 subset, Rawls24, A0 versus A1,
and three timing repetitions. It establishes exact agreement and real-case performance,
not large-scale scalability.

### E5-B Scenario scalability

Use 30 nested replicates at |Omega|=`50,100,200,500`, |I|=3. For replicate r,
generate one 500-scenario master pool and take nested prefixes/subsets; use one Q-F-R
draw for all four sizes. A synthetic scenario selects a Rawls24 template, inherits its
category, and sets `d_i_syn=d_i_template*m_common*m_i`, with
`m_common~U(.85,1.15)` and item multipliers independently `U(.95,1.05)`. Category and
availability use the instance's frozen rho_Q/rho_F/eta/economic parameters. Compute
one `B_r^bench` from the full 500 pool and use it unchanged at every nested size.
These distributions are computational benchmark rules, not hurricane probabilities.

### E5-C Commodity scalability

Use |I|=`3,6,9`, |Omega|=100, and 30 nested replicates from a 9-item master pool.
Archetype counts are `1+1+1`, `2+2+2`, and `3+3+3`. Item cost and reference-demand
multipliers are `U(.8,1.2)`. Standard has h=0,a=1; Preservation has a=1 and
`h_j*tau=m_h*(h*tau)_base`, `m_h~U(.5,1.5)`; StorageLoss has h=0 and
`a_j~U(.80,1.00)`. A benchmark instance shares one Q-F-R mechanism draw across all
items. Each item-size instance uses `B/B_ref^bench=1` under the same definition.

The exact representative-subset algorithm, E5 replicate seeds, template-selection
measure, and nested ordering/tie policy remain `OPEN_DECISION_E5_GENERATOR_IDENTITY`.
The stated sizes and distributions are frozen, but execution is blocked until those
identities are supplied; the scientific E4-B generator must never be substituted.

## 8. Reuse, failure, and governance rules

- A result is reusable only if every scientific identity matches or a historical
  implementation difference is proven inert on the complete saved trace.
- Failure, timeout, infeasible, numerical, and certificate failures remain in their
  original sample identities; no replacement or result-driven resampling is allowed.
- No parameter range, generator, tolerance, or algorithm setting may be changed in
  response to policy shares, activation, runtime, or aesthetic preference.
- Scientific and computational generators have separate identities and claims.
- Exact sample/data/config/source/output hashes and git/tree/solver identities are
  mandatory. Generated evidence never silently becomes protocol authority.

## 9. Open decisions and execution gate

1. `OPEN_DECISION_REPRESENTATIVE_SPACE_FILLING`: exact deterministic 200/100-row
   subset construction and tie rules.
2. `OPEN_DECISION_E3B_RELIABILITY_SELECTION`: row-level F-active membership,
   z-score population, tie handling, and de-duplication.
3. `OPEN_DECISION_E4B_GENERATOR`: complete Rawls24 scientific OOS generator and seeds.
4. `OPEN_DECISION_E5_GENERATOR_IDENTITY`: replicate seeds, template sampling,
   nested ordering, and exact benchmark generator identity.
5. `OPEN_DECISION_PR27_ENGINEERING_PROMOTION`: independent approval of generic
   numerical-validation and no-memory execution adapters before Formal execution.

No E1–E5 execution is authorized by this document. PR #27 is not merged by this
re-freeze. The companion PR27 audit determines result reuse candidacy only.
