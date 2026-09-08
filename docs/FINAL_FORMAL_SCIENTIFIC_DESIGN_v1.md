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

Select one shared `N_E3=200` subset from the frozen E1 table. Normalize each of the
16 continuous parameters independently by its theoretical Final E1 marginal bounds,
then use Euclidean distance. The first actual row is nearest the all-0.5 geometric
center; subsequent rows maximize their minimum distance to the selected set. Ties
within eight IEEE-754 ULPs are resolved by minimum `sample_index`. Policy, objective,
shortage, runtime, worst scenario, R activation, and candidate hits are forbidden
selection inputs. The ordered IDs and identity hash are frozen in
`docs/evidence/FINAL_FORMAL_MACHINE_IDENTITIES_v1.json`.

### E3-A Storage burden x F economics

Cross Vaccine `h_V*tau={0,.50,1.00}` with `m_F={.8,1,1.2}` applied jointly to
the reference `(phi,psi)=(.20,.85)`. The three F pairs are `(.16,.68)`,
`(.20,.85)`, and `(.24,1.02)`. Maximum 1,800 optimizations; duplicate baseline
cells may be reused.

### E3-B F supply risk x reliability economics

For every one of the 1,000 frozen E1 rows, compute `S_F=(1/5)*sum_k(1-rho_F,k)`.
Using NumPy's linear empirical quantile definition, select actual full rho_F curves
nearest Q25/Q50/Q75 as Low/Medium/High supply risk without using outcomes. Process
quantiles in that order, remove each selected row, and break numerical ties by the
same eight-ULP/minimum-ID rule.

Reliability economics is restricted to rows for which at least one nonnegative
commodity F quantity exceeds the E1 policy tolerance `1e-7`. F quantities are used
only for this filter. Compute A_R1 and A_R2 as above, standardize each across all
F-active rows with population SD (`ddof=0`), and set
`A_R=.5*(Z(A_R1)+Z(A_R2))`. Zero SD stops with
`E3B_RELIABILITY_SCORE_DEGENERATE`. Linear empirical Q25/Q50/Q75 define
Unfavorable/Reference/Favorable; process in order, exclude used rows, and apply the
same tie rule. R label, objective, shortage, and runtime cannot enter selection.
The frozen rows are recorded in the machine-identity evidence. Maximum: 1,800
optimizations. E3 theoretical maximum: 3,600.

## 6. E4 — Out-of-Sample Robustness

### E4-A Historical LOHO

Use the same eventual deterministic outcome-independent 200-row subset. For each of
24 hurricanes, optimize on the other 23 and evaluate the held-out event: 4,800
training optimizations. Every fold uses absolute `B_ref^E1`; leave-one-out budget
recalculation is prohibited. Preserve held-out T-COST, shortage, service level,
regret, policy change, and full24-versus-LOHO policy comparison.

### E4-B Synthetic OOS

Select `S_100` from within `S_200` using the same normalized-Euclidean center/maximin
rule; it is not independently selected from all 1,000 rows. The scientific generator
is `RAWLS24_SCIENTIFIC_OOS_GENERATOR_V1`, separate from every E5 generator. For each
seed `20260904` through `20260913`, generate 2,000 scenarios shared by all 100 policies.
Each scenario draws a Rawls24 template uniformly, inherits its category, draws one
shared `U(.85,1.15)` disaster multiplier, then independent `U(.95,1.05)` multipliers
in Water/Vaccine/Crackers order. The RNG is NumPy Generator(PCG64), and draw order is
template, common, Water, Vaccine, Crackers. The bands are pre-specified stress bands,
not empirical estimates. No no-hurricane or extra availability noise is generated;
the policy row's rho_Q/rho_F and formal R-to-F mapping apply.

Q/F/R remain fixed and only formal second-stage recourse is evaluated. Pre-registered
metrics are mean/P90/P95 T-COST, mean/P95 shortage, probability of any shortage above
the policy tolerance, mean service, and P05 service, with
`SL=1-sum_i(u_i)/sum_i(d_i)`. This protocol freezes metrics but authorizes no OOS run.

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

Use seeds `20261001` through `20261030` for 30 nested replicates at
|Omega|=`50,100,200,500`, |I|=3. The first PCG64 draw selects a uniform integer E1
parameter row from 1..1000, shared by all four sizes. For replicate r,
generate one 500-scenario master pool and take nested prefixes/subsets; use one Q-F-R
draw for all four sizes. A synthetic scenario selects a Rawls24 template, inherits its
category, and sets `d_i_syn=d_i_template*m_common*m_i`, with
`m_common~U(.85,1.15)` and item multipliers independently `U(.95,1.05)`. Category and
availability use the instance's frozen rho_Q/rho_F/eta/economic parameters. Compute
one `B_r^bench` from the full 500 pool and use it unchanged at every nested size.
These distributions are computational benchmark rules, not hurricane probabilities.
The generator identity is `RAWLS24_E5B_COMPUTATIONAL_BENCHMARK_GENERATOR_V1`.

### E5-C Commodity scalability

Use seeds `20261101` through `20261130`, |I|=`3,6,9`, |Omega|=100, and 30 nested
replicates from a 9-item master pool. The first PCG64 draw uniformly selects one E1
parameter row shared by all item sizes. Master order is exactly Standard_1,
Preservation_1, StorageLoss_1, then the same archetype order for suffixes 2 and 3;
the 3/6/9 instances are generation-order prefixes.
Archetype counts are `1+1+1`, `2+2+2`, and `3+3+3`. Item cost and reference-demand
multipliers are `U(.8,1.2)`. Standard has h=0,a=1; Preservation has a=1 and
`h_j*tau=m_h*(h*tau)_base`, `m_h~U(.5,1.5)`; StorageLoss has h=0 and
`a_j~U(.80,1.00)`. A benchmark instance shares one Q-F-R mechanism draw across all
items. For every item the fixed draw order is m_c, m_d, then the archetype-conditional
m_h or a draw; Standard consumes no third draw. After the complete item pool, generate
one shared 100-scenario master table. Each scenario uniformly selects one of h01–h24,
inherits its category, excludes no-hurricane, and draws one common
`m_common~U(.85,1.15)` shared by every item. Standard maps to the template's Water
baseline, Preservation to Vaccine, and StorageLoss to Crackers. Its demand is
`d_j,omega=d_template,archetype(j)*m_d,j*m_common,omega`; m_d,j is fixed over all
100 scenarios and there is no item-by-scenario multiplier. The full RNG order is
parameter row, all nine item draws, then template ID and common shock for scenarios
1..100. I=3/6/9 use item prefixes against the identical scenario table.

Each item-size instance separately computes its benchmark B_ref from its item prefix
and this shared demand table, then uses `B/B_ref^bench=1`. The generator identity is
`RAWLS24_E5C_COMMODITY_BENCHMARK_GENERATOR_V1`. It is computational and cannot be
substituted for E4-B.

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

## 9. Machine identities and execution gate

All Formal scientific machine-definition decisions are resolved. Exact selections,
per-seed generated-input hashes, selected parameter-row IDs, nesting hashes, and
generator hashes are frozen in `docs/evidence/FINAL_FORMAL_MACHINE_IDENTITIES_v1.json`.
The deterministic implementation is `robust_budget_allocation.formal.final_design`.
`OPEN_DECISION_PR27_ENGINEERING_PROMOTION` remains a non-scientific governance gate:
generic numerical-validation and no-memory execution adapters still require independent
approval before promotion. It does not reopen any scientific design rule.

No E1–E5 execution is authorized by this document. PR #27 is not merged by this
re-freeze. The companion PR27 audit determines result reuse candidacy only.
