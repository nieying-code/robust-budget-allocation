# R5 Q-F-R Pilot & Mechanism Diagnosis Report v2

Status: **PILOT COMPLETED / READY FOR INDEPENDENT REVIEW / R6 NOT AUTHORIZED**

## 1. Scope and provenance

R5 started from merged main commit `5017b16f4f8b354adc2d18dd03c88cadc09fa556`, tree `2d3a79999cd6ebfd2e96129e484b3831dd4f3d76`. The Pilot protocol, Excel reader, execution config and runner were frozen before the first solve in commit `5899d2fb98dafb619489efb796ae4186b3b27706`, tree `4c877bb07e34c6b6cf4ddab77dcffbcffdc1d9bd`. Protocol SHA-256 is `5c20518a6dcb586838bf0a4b4980154059f82b7c1732df324d5ae3df43ae617b`.

This is one deterministic mechanism-diagnosis Pilot, not a formal experiment, OOS evaluation, performance study, or formal parameter freeze. No Q-F-R model equation, EF/A0/A1 logic, Memory, Candidate ranking, exact certification, tolerance, solver policy, scenario, budget ratio or frozen scientific parameter was changed.

## 2. WFP Syria Excel source audit

Actual source path: `D:\新建文件夹\项目：robust-budget-allocation\Data Syria Case WFP.xlsx`.

Workbook SHA-256: `f3e604eb3000d20e0e7eb64c7f847b6e34b83b85a417031a77805b8ea614c55b`.

The runner read the workbook itself and validated all six sheets: `Nodes - Types`, `Edges - Cost`, `Food - Nutritional value`, `Food - Cost`, `Food - InternationalPrice`, and `Nutrient - Requirements`.

`Nodes - Types` contains exactly seven demand nodes: Ar Raqqa 10,000; Daraa 10,000; Dayr_Az_Zor 25,000; Hassakeh 10,000; Idleb 5,000; Jubb_al_Jarrah 2,000; Qamishli 5,000. Total: 67,000.

Sugar and Rice both have raw rows in the nutritional, cost and international-price sheets. The nutritional records are Sugar `(400 kcal; all listed non-energy nutrients zero)` and Rice `(360 kcal, 7 g protein, 0.5 g fat, 7 mg calcium, 1.2 mg iron, ...)`. International-price raw fields are Sugar `1100` and Rice `800`; these source descriptors do not replace the separately frozen USD/SU Q costs. Each commodity has cost rows for eight Syrian jurisdictions and 472 dated/mean value cells. No Excel/frozen-baseline conflict was found.

## 3. Pilot matrix and correctness

All nine registered cases completed: three models × budget ratios 0.90, 1.00, 1.10. Every case ran EF, A0 and the existing A1.

| Budget ratio | M0 objective | M1 objective | M2 objective | Worst scenario |
| ---: | ---: | ---: | ---: | --- |
| 0.90 | 759,001.65 | 742,217.15 | 734,731.94 | `omega_4` |
| 1.00 | 694,859.60 | 681,972.04 | 674,917.86 | `omega_4` |
| 1.10 | 630,717.54 | 621,726.94 | 616,805.81 | `omega_4` |

Maximum EF/A0/A1 objective difference was `1.1641532182693481e-10`; maximum feasibility violation was `5.820766091346741e-11`. All nine certificates passed the unchanged numerical policy. Different optimal first-stage vectors, where present, were handled under the existing multiple-optima policy; every stored decision was independently feasible and certified.

## 4. Canonical EF mechanism allocations

Item tuple order is `(Sugar, Measles Vaccine, Rice)`. Reliability is reported only where F is positive; `R0/R1/R2` correspond to eta `0.20/0.50/0.80`.

| Case | Q tuple | F tuple | Active reliability | C_Q | C_F | C_R | Worst emergency cost | Worst shortage cost | Worst budget usage |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0.90_M0 | (94,588.24, 0, 62,127.41) | (0, 0, 0) | — | 275,682.19 | 0 | 0 | 0 | 483,319.46 | 275,682.19 |
| B0.90_M1 | (94,588.24, 0, 45,841.48) | (0, 0, 22,937.93) | Rice R0 | 217,052.85 | 16,515.31 | 0 | 42,114.03 | 466,534.96 | 275,682.19 |
| B0.90_M2 | (94,588.24, 0, 0) | (0, 11,256.00, 65,345.74) | Vaccine R0; Rice R1 | 52,023.53 | 47,926.90 | 23,524.47 | 152,207.29 | 459,049.74 | 275,682.19 |
| B1.00_M0 | (94,588.24, 0, 70,636.12) | (0, 0, 0) | — | 306,313.55 | 0 | 0 | 0 | 388,546.05 | 306,313.55 |
| B1.00_M1 | (94,588.24, 0, 58,131.38) | (0, 0, 17,612.30) | Rice R0 | 261,296.50 | 12,680.86 | 0 | 32,336.19 | 375,658.50 | 306,313.55 |
| B1.00_M2 | (94,588.24, 0, 18,377.90) | (0, 0, 55,742.10) | Rice R1 | 118,183.97 | 40,134.31 | 20,067.15 | 127,928.11 | 368,604.32 | 306,313.55 |
| B1.10_M0 | (94,588.24, 0, 79,144.83) | (0, 0, 0) | — | 336,944.90 | 0 | 0 | 0 | 293,772.64 | 336,944.90 |
| B1.10_M1 | (94,588.24, 0, 70,421.28) | (0, 0, 12,286.68) | Rice R0 | 305,540.15 | 8,846.41 | 0 | 22,558.34 | 284,782.04 | 336,944.90 |
| B1.10_M2 | (94,588.24, 0, 42,688.50) | (0, 0, 38,886.75) | Rice R1 | 205,702.13 | 27,998.46 | 13,999.23 | 89,245.08 | 279,860.91 | 336,944.90 |

The complete item-level `x[i,omega]`, `u[i,omega]`, emergency cost, shortage cost, unused cash and budget usage for every one of the 45 case-scenario pairs are preserved under `cases[].diagnostic.scenarios` in `docs/evidence/R5_QFR_PILOT_RESULTS_v2.json`. The worst scenario is `omega_4` in every case. Its item-level shortages are dominated by Rice and Vaccine; Sugar shortage is zero in every worst-case solution.

## 5. Diagnostic answers

**A. F activation.** Yes. F activates naturally in all six M1/M2 cases, without any retuning. M1 uses Rice F at R0. M2 uses Rice F at R1 in all budgets and also Vaccine F at R0 only in B0.90.

**B. R activation.** Yes. Paid reliability activates naturally in every M2 case: Rice selects R1. R2 is never selected. No R acts independently of positive F.

**C. Commodity heterogeneity.** The allocations are strongly heterogeneous. Sugar is served entirely by Q because it combines low Q cost, full retention and zero storage burden. Rice uses a Q/F mix; its high Q cost and 0.91 retention make F valuable, and M2 protects Rice F at R1. Vaccine receives F only in B0.90_M2 and otherwise remains shorted. The frozen shortage coefficient `s_i=4*cQ_i` gives Vaccine the lowest absolute per-unit shortage penalty, while Rice has the highest; this helps explain the allocation priority without changing the registered parameters.

**D. Model progression.** Objectives strictly improve `M0 > M1 > M2` at every budget. M1 adds base flexible Rice supply. M2 adds R1 protection and further reduces the objective. The incremental objective reduction becomes smaller as the budget increases; this is a Pilot observation only.

**E. Budget response.** Higher budgets reduce objectives and worst-case shortage costs in all models. For Rice, higher budgets shift the allocation toward more Q and less F. Worst-scenario cash usage is binding to numerical tolerance in all nine cases. The response is coherent under the frozen accounting, but it does not imply a formal monotonicity theorem.

**F. EF/A0/A1 correctness.** PASS for all M0/M1/M2 and budgets within the frozen tolerance and feasibility policy.

**G. A1 Memory/Candidate behavior.** A0 used 24 iterations, 24 Full Exact calls and 120 scenario evaluations. A1 used 42 iterations, 9 Full Exact Certification calls and 81 scenario evaluations. Memory opportunities/hits were `0/0`; Candidate hits were `33`. Candidate Search was active, while this Pilot trajectory does not identify Memory value. Workload and runtime are descriptive metadata, not performance claims.

Aggregate measured runtime was EF `0.5731 s`, A0 `1.0374 s`, A1 `0.9587 s`. No speedup or scalability inference is made.

**H. OPEN DECISION.** `OPEN_DECISION_R5_01` is deferred to the researcher before R6: Vaccine is fully shorted in eight of nine canonical EF allocations and increasing the budget does not improve Vaccine service under M0/M1 or the two higher-budget M2 cases. R5 does not determine whether this is an acceptable expression of the frozen `s_i=4*cQ_i` calibration or whether a future redesign/calibration review is scientifically warranted. No parameter was changed in response.

## 6. Scope audit

- Pilot batches: 1; Pilot cases: 9.
- Formal experiment design: 0.
- Formal experiments: 0.
- OOS runs: 0.
- A1 changes: 0.
- Post-result parameter/scenario/tolerance changes: 0.

R6 is not authorized. This delivery stops at independent review.

## 7. Validation

- Focused R5/delivery/historical replay checks: `15 passed`.
- Full solver-free regression with the registered workbook available: `888 passed, 106 deselected`.
- Full licensed regression: `106 passed, 888 deselected`.
- Final R5 evidence replay: PASS.
- Historical revision/R3/R4 delivery checks: PASS.
- `git diff --check`: PASS.

Environment: CPython 3.12.10, Pyomo 6.10.1, gurobipy/Gurobi 13.0.2, `gurobi_direct`, Threads=1, no fallback.
