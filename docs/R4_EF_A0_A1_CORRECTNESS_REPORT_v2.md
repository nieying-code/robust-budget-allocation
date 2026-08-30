# R4 Improved C&CG + Correctness Report

Status: **R4 delivery — ready for independent review after Draft PR creation**

Scope: a model-independent improved exact C&CG for the merged heterogeneous-material Q-F-R v2 models, plus small deterministic EF≈A0≈A1 correctness and workload evidence. This is not a pilot, formal experiment, OOS evaluation, speed claim, scalability claim, or scientific result.

## 1. Governance and frozen inputs

- R4 base merge commit: `1cbce8b828e5b0494f9bef4b147358a379b91b18`;
- base tree: `90aead8ecfe381fdb9e0012f85eaa6fa8bbb7c9d`;
- branch: `r4/a1-improved-ccg`;
- R4 protocol freeze commit: `e314237f4ae1bb1bd4a0495af7bfaa10d0092e3a`;
- protocol freeze tree: `8608d24339cbabc797a4b17d6115e35a9a0c3cb4`;
- protocol SHA-256: `5b493b3844210bb63180575ffc2dde5d74a883f75c93a9e8374b58f61b5306a6`;
- correctness execution commit: `4ff6c15c75a07787a8e2fa6cf4be5ce67687350a`;
- correctness execution tree: `01224ef1cf2377ba6a832ed8fe4fb81d16027c50`.

The protocol was committed before A1 implementation and before any licensed R4 correctness run. R3's frozen tolerance, deterministic scenario rules, Gurobi numerical settings, accepted status, R2 model, R3 EF/A0, exact recourse, and full finite-scenario oracle are unchanged.

## 2. Reuse boundary and A1 structure

Historical `a1_memory.py`, `a1_candidates.py`, and `memory_guided_ccg.py` remain unchanged and are not imported by the v2 path. R4 adapts only generic solve-local history, deterministic candidate-container limits, exact partial evaluation, and the full-certification boundary.

The old shortage-exposure score is not inherited. Candidate ranking is canonical scenario ID only and uses no Q/F/R economics, scientific parameter proxy, ML, dominance screening, or adaptive candidate size.

The preregistered structure was:

`Memory Inspection -> Candidate Search -> Full Exact Certification`.

Only a complete Full Exact Certification over all Ω can identify the formal worst scenario, update formal UB, or certify convergence. The restricted-master exact optimum supplies LB. Memory/Candidate exact hits may add a currently violated scenario but cannot update UB or terminate the algorithm.

## 3. Memory decision

Across the complete preregistered M0/M1/M2 trajectory:

- memory opportunities: 0;
- memory hits: 0;
- candidate hits: 6.

The frozen rule therefore records `MEMORY_VALUE_NOT_IDENTIFIED_NONBLOCKING` and retains Memory provisionally. No dedicated Memory ablation or additional experiment was run. The absence of opportunities occurs because Candidate Search added the two omitted scenarios before the first Full Exact Certification; the algorithm then certified and stopped, so solve-local exact history was never eligible at a later master.

## 4. Correctness results

The unchanged R3 three-item, three-scenario fixture remains marked `CORRECTNESS_FIXTURE_ONLY_NOT_FORMAL_SCIENTIFIC_PARAMETERS`.

| Model | EF objective | A0 objective | A1 objective | Maximum difference | A0 iterations | A1 iterations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| M0 = Q | 535.9097744360902 | 535.9097744360902 | 535.9097744360902 | 0 | 2 | 3 |
| M1 = Q+F | 535.9097744360902 | 535.9097744360903 | 535.9097744360902 | 1.1368683772161603e-13 | 2 | 3 |
| M2 = Q+F+R | 510.3732625331875 | 510.3732625331876 | 510.3732625331875 | 5.684341886080802e-14 | 2 | 3 |

Aggregate:

- accepted EF/A0/A1 comparisons: 3/3;
- maximum objective difference: `1.1368683772161603e-13`;
- maximum feasibility violation: `0`;
- A0 iterations: 6;
- A0 full exact calls: 6;
- A0 scenario evaluations: 18;
- A1 iterations: 9;
- A1 full exact certification calls: 3;
- A1 scenario evaluations: 15;
- memory opportunities/hits: 0/0;
- candidate hits: 6.

The lower counts are recorded only as correctness-stage workload observations. They do not establish speedup, scalability, statistical superiority, or algorithmic novelty.

## 5. Evidence and replay

The original first Memory trajectory remains unchanged at `docs/evidence/R4_A1_INITIAL_MEMORY_TRAJECTORY_v2.json`, sealed SHA-256 `4a9f14e1a5c4b98bf2611e3b68a0385d90a1d906603d321f4aaa5a84fe739123`. It is retained as preregistered decision provenance and is not overwritten.

After independent-review fixes, final correctness evidence was rerun from clean execution commit `14f99cccd46871f46ea10e36b15412cadb70bddf`, tree `a34df46f367dbe6b8c6e28d0d593e139ec0aecf1`:

- path: `docs/evidence/R4_EF_A0_A1_CORRECTNESS_FINAL_v2.json`;
- sealed SHA-256: `5f70d41ca9e52dc54301474ad657cc20af31a85421394ed4a1c979597a9aea07`.

The repair closes `outer model_kind = EF = A0 = A1 = certificate`, binds certificates to all three result seals, checks Full Exact Certification theta against the same master theta, records and verifies certification iteration/decision ownership, and permits formal UB/incumbent/convergence fields only on iterations that actually ran Full Exact Certification. Candidate/Memory-hit iterations store those non-applicable fields as null.

Replay validates the execution commit/tree and source inventory, unchanged fixture, locked solver environment/policy, every EF/A0/A1 result, restricted-master accounting and LB, partial exact evaluations, legal additions, formal UB ownership, complete final Ω certification, convergence, counters, summary, and the conditional Memory decision.

Final tests:

- focused solver-free R4 and review-negative tests: `19 passed, 3 deselected`;
- focused licensed R4 correctness: `3 passed, 7 deselected`;
- full solver-free regression: `850 passed, 105 deselected`;
- full licensed regression: `105 passed, 850 deselected`;
- final evidence replay: PASS;
- `git diff --check`: PASS.

## 6. Scope audit and limitations

- No R2 model file or R3 EF/A0 implementation changed.
- No historical A1 file changed or imported.
- No QFR-specific candidate score was introduced.
- Scientific runs = 0; pilot runs = 0; formal experiments = 0; OOS runs = 0.
- Runtime is metadata only.
- Memory value was not identified because opportunities were zero; this is nonblocking under the preregistered rule.
- R5 is not authorized or started.
- Scientific/model/algorithm outputs and workload counters are unchanged by the review repair.

Final delivery commit/tree and Draft PR remain external anchors to avoid self-referential delivery hashes.
