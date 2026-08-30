# R5 Q-F-R Pilot & Mechanism Diagnosis Protocol v2

Status: `FROZEN_BEFORE_FIRST_R5_PILOT_SOLVE`

Scope: one deterministic diagnostic Pilot for the merged Q-F-R availability revision. This protocol does not authorize formal experiment design, OOS evaluation, parameter retuning, model changes, or A1 changes.

## 1. Source and configuration identity

The Pilot must read the local source workbook named `Data Syria Case WFP.xlsx` and require SHA-256 `f3e604eb3000d20e0e7eb64c7f847b6e34b83b85a417031a77805b8ea614c55b`. It must audit the workbook itself rather than treating copied JSON values as the source.

Required workbook facts are registered in `configs/r5_pilot_execution_v2.json`: six named sheets; seven demand nodes totaling 67,000; and raw Sugar/Rice records in the nutritional, cost, and international-price sheets. Workbook international-price fields remain raw source descriptors and do not replace the separately frozen USD/SU Q costs.

Scientific inputs are exactly `configs/qfr_pilot_baseline_v2_1.json`: Sugar, Measles Vaccine, Rice; five frozen joint scenarios; budget ratios 0.90, 1.00, 1.10; and the already frozen Q/F/R costs, retention, availability, disruption, reliability and shortage parameters. No sixth scenario is permitted.

## 2. Run matrix

The matrix contains exactly nine cases in deterministic order: each budget ratio in `(0.90,1.00,1.10)`, and within each ratio `M0`, `M1`, `M2`. Every case runs EF, A0 Standard C&CG, and the existing R4 A1 with Memory enabled. The existing model builders, fixed-budget accounting, exact oracle, R3 numerical tolerance, solver configuration, A1 Memory, Candidate Search and Full Exact Certification are unchanged.

Licensed execution remains CPython 3.12.10, Pyomo 6.10.1, gurobipy/Gurobi 13.0.2, `gurobi_direct`, Threads=1, no fallback, with the frozen R3/R4 numerical options and accepted statuses.

## 3. Required correctness and diagnostics

For every case, the existing certificate must revalidate EF/A0/A1 objective agreement and feasibility. Multiple optimal first-stage vectors are not rejected solely for differing values; each stored solution must independently validate.

The EF solution is the canonical mechanism-diagnosis allocation. The delivery records Q, F, selected reliability level, Q/F/R first-stage costs, every scenario's exercise and shortage by item, emergency and shortage cost, unused cash, worst scenario, objective, and maximum violation. It also records all EF/A0/A1 objectives, first-stage decisions, runtime, A0 iterations/full exact calls/scenario evaluations, and A1 iterations/Memory opportunities and hits/Candidate hits/Full Exact Certification calls/scenario evaluations.

Runtime and workload are descriptive Pilot metadata only. No speedup, scalability or formal statistical claim is permitted.

## 4. Diagnostic and failure policy

The Pilot answers whether F and R activate naturally, whether commodities differ, whether M0→M1→M2 and budgets show interpretable responses, whether EF≈A0≈A1 remains valid, and whether A1 Memory/Candidate are used.

No result may trigger parameter, scenario, budget, fixture, tolerance, model, or algorithm changes inside R5. Nonactivation, homogeneous decisions, small model differences, or weak budget response must be preserved and reported. Any proposed scientific change becomes an OPEN DECISION for the researcher.

A failed solver status, incomplete exact oracle, certificate failure, workbook/config identity mismatch, or frozen-input mismatch stops the run. Completed failures are retained; failed cases are not replaced or hidden.

## 5. Scope exclusions

- Formal experiment design and formal parameter freeze: not run.
- OOS evaluation: not run.
- Formal experiments: not run.
- A1 modification or renaming: prohibited.
- Pilot-driven retuning: prohibited.

