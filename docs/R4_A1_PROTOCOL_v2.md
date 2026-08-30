# R4 A1 Improved C&CG Protocol v2

Status: **FROZEN BEFORE R4 IMPLEMENTATION AND LICENSED CORRECTNESS RUNS**

Authority: the user explicitly authorized R4 and selected the generic A1 structure and conditional Memory-retention rule. This document registers that new v2 mechanism. It does not reactivate the historical Q-R-F/F-OPTION model, its candidate score, fixtures, evidence, results, or conclusions.

## 1. Shared reviewed foundation

A1 uses the merged R2 Q-F-R M0/M1/M2 formulation and the merged R3 restricted master, exact recourse, full finite-scenario oracle, numerical tolerance, deterministic rules, solver settings, and accepted-status policy without modification.

The R3 tolerance remains:

`T(a,b) = 1e-7 + 1e-9 * max(1, abs(a), abs(b))`.

Licensed solves remain `gurobi_direct`, Threads=1, no fallback, MIPGap=0, MIPGapAbs=0, and FeasibilityTol/OptimalityTol/IntFeasTol=1e-9. Only `SolverStatus.ok` with `optimal` or `globallyOptimal` is accepted.

## 2. Provisional three-stage structure

The preregistered first implementation is:

1. Phase I — Memory Inspection;
2. Phase II — Candidate Search;
3. Phase III — Full Exact Certification.

Memory and Candidate evaluations solve the unchanged exact single-scenario recourse at the current master decision. A hit requires a current exact violation greater than the frozen `T`. Neither phase may set a formal UB, certify convergence, or replace Phase III.

Only a complete Phase III evaluation of every scenario in canonical order may identify the formal worst scenario, update formal UB, or certify convergence. Formal LB is the current restricted-master exact optimum. The iteration safety limit remains `len(Omega)+1`.

## 3. Generic solve-local Memory

Memory is empty at the start of each solve and is never shared across models, instances, runs, budgets, threads, OOS, or evidence replay. An entry contains only complete data identity, canonical scientific scenario identity, last exact recourse loss, last evaluated iteration, and evaluation source. Cached loss is ordering history only and is never treated as recourse at a new first-stage decision.

The generic historical constants are re-registered unchanged: capacity 8, maximum age 4 iterations, and inspection limit 2. Invalid, stale, wrong-data, unknown-scenario, current/future-iteration, or malformed entries are removed. Eligible nonactive entries are ordered by descending last exact loss, descending last iteration, then canonical scenario ID. Planned entries are evaluated exactly at the current decision and inspection stops at the first exact violation.

Counters record `memory_opportunities` as the number of iterations with at least one eligible planned Memory scenario and `memory_hits` as exact violating scenarios selected by Phase I.

## 4. Model-independent Candidate Search

The old shortage-exposure score is Q-R-F-specific and is not inherited. No Q/F/R economics, demand-shortage proxy, reliability meaning, learned weight, dominance rule, or adaptive limit enters Candidate ranking.

Candidate Search reuses only the generic container/evaluation logic: its pool is every complete-Omega scenario not active and not already evaluated by Memory at the current decision; exclusions are recorded; ranking is canonical scenario ID order; and at most one candidate is evaluated exactly. It stops on the first exact violation. An empty pool or miss falls through to Full Exact Certification and never means convergence.

`candidate_hits` counts exact violating scenarios selected by Phase II.

## 5. Conditional Memory retention rule

After the first complete preregistered M0/M1/M2 correctness trajectory:

- if aggregate `memory_opportunities > 0` and `memory_hits = 0`, the independent Memory phase is removed and final A1 is `Candidate Search -> Full Exact Certification`;
- if aggregate `memory_hits > 0`, Memory is retained;
- if aggregate `memory_opportunities = 0`, Memory is retained provisionally and the absence of identification is recorded as a nonblocking limitation.

The first trajectory and this decision provenance must be preserved. If Memory is removed, all M0/M1/M2 correctness cases are rerun from the final clean implementation. No fixture, tolerance, solver setting, ranking, or scientific parameter may be changed in response.

## 6. Exactness and bounds

Each iteration solves the restricted master exactly. `LB_k` is that master optimum; heuristic phases do not alter it. Only Phase III produces `candidate_UB = C_pre + max_omega recourse_omega`; the formal UB is the best such complete certificate with producing iteration and decision retained.

Memory/Candidate hits may add one nonactive complete-identity scenario and continue without a new UB. Certification requires a just-completed full exact Phase III and both:

`-T(UB,LB) <= UB-LB <= T(UB,LB)`

and current exact-oracle violation within its frozen tolerance. Duplicate additions, crossed bounds, incomplete oracle, unexplained no-progress, or iteration exhaustion fail closed.

## 7. Correctness and workload evidence

The unchanged R3 deterministic heterogeneous multi-item fixture is used only for M0/M1/M2 correctness. Each case must validate EF≈A0≈A1 objective agreement, independent feasibility/accounting, formal bounds, legal additions, and final full exact certification. Multiple optimal first-stage vectors are accepted without arbitrary vector equality.

Workload metadata records A0/A1 iterations, A1 memory opportunities/hits, candidate hits, full exact certification calls, and total scenario evaluations. These are correctness-stage observations only—not speed, scalability, statistical, or scientific claims.

## 8. Scope exclusions

R4 does not modify the Q-F-R model, R3 EF/A0 formulation, fixture science, tolerance, or solver policy. It adds no QFR-specific ranking, ML, dominance screening, adaptive candidate size, pilot, OOS scientific evaluation, formal experiment, parameter tuning, or R5 work.
