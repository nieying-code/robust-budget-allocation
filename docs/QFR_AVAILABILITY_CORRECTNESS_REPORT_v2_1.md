# Q-F-R Availability Revision Correctness Report v2.1

Status: **READY FOR INDEPENDENT REVIEW; PILOT NOT STARTED**

## 1. Scope and provenance

This delivery revises the merged pre-revision Q-F-R model at base commit `85edaffded8e8853d6357a8b92a540e36f7ec233`, tree `9f755fb2e1d7271ba34edffb3720184feb40b4da`. The old R0–R4 specifications, protocols, evidence, and hash inventories remain unchanged historical provenance.

The new scientific/model revision was frozen in commit `b5a44908d992ab2b1267ff0067eb78a1ff439c73`, tree `e129d20c4d43e72f38bdd60a349ac5ad90481329`. The correctness protocol SHA-256 is `2ff46393109fab00710e6dfebcf5a3ef17ad3376bcdf4528a3db068ebe05f800`.

Final correctness execution used clean commit `be10c47d5b26a96bd767b07f96396c10ad752e1e`, tree `0c66bc237dadbe736e526181933cde6280dff59e`.

## 2. Scientific and implementation changes

- Added complete item/scenario `q_availability` with production domain `[0,1]` and inclusion in canonical data/scenario identity.
- Demand service now uses `retention[i] * q_availability[omega][i] * Q[i]` in M0/M1/M2, independent accounting, and exact recourse.
- Revised schema version 3 requires `0 < eta[0] < eta[1] < eta[2] < 1`; schema version 2 is retained explicitly for historical replay with unit Q availability and its original hashes.
- M1 uses positive base fulfillment at level 0 with zero reliability premium; M2 restricted to level 0 remains structurally and numerically identical to M1.
- EF, A0, and A1 algorithm/state-machine files were not mathematically redesigned. They consume the revised shared data, model, scenario identity, accounting, and exact recourse paths.
- A frozen pilot configuration constructor computes `h_vaccine=0.08/6`, `B_ref=306313.545054945`, the five registered joint scenarios, costs, and `Fbar_i=max_omega d[i,omega]`. It was constructed and validated only; it was not solved as a pilot.

## 3. Correctness results

The deterministic three-item fixture is marked correctness-only and is not the pilot baseline. All cases have positive Q; M1/M2 have positive F and exercise; shortage is positive; Q availability includes 1.00, 0.85, and 0.70.

| Model | EF objective | A0 objective | A1 objective | Worst scenario | A0 iterations | A1 iterations |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| M0 | 643.9097744360902 | 643.9097744360903 | 643.9097744360903 | `c_severe` | 2 | 3 |
| M1 | 632.0057744360902 | 632.0057744360903 | 632.0057744360902 | `c_severe` | 2 | 3 |
| M2 | 544.13 | 544.13 | 544.13 | `c_severe` | 2 | 3 |

Maximum EF/A0/A1 objective difference is `1.1368683772161603e-13`; maximum feasibility violation is `0`. Every A0 and A1 terminates by valid Full Exact Certification and frozen LB/UB tolerance. Programmatic nesting licensed checks pass for `M1|F=0=M0` and `M2|levels={0}=M1`.

Correctness-stage workload metadata only:

- A0: 6 iterations, 6 full exact calls, 18 scenario evaluations.
- A1: 9 iterations, 3 Full Exact Certification calls, 15 scenario evaluations.
- Memory opportunities/hits: 0/0; Candidate hits: 6.

No runtime, speedup, scalability, mechanism-value, or pilot conclusion is drawn.

## 4. Evidence and failures retained

Final evidence: `docs/evidence/QFR_AVAILABILITY_CORRECTNESS_FIRST_RUN_v2_1.json`.

Evidence seal: `be50da5981c1fec4de240a3c48e8fd2a69b7fb3a69cf7f89d91d435e27dc3ca6`. Replay: PASS.

Two earlier complete solve attempts were rejected before evidence write by wrapper implementation gates, not numerical correctness:

1. a copied protocol hash omitted one hexadecimal character;
2. an ordered tuple from existing `validate_source_state` was compared directly with a list.

Both failure records are preserved. Only the copied identity/container interpretation was corrected; scientific fixture values, model, EF/A0/A1 logic, tolerance, and solver policy were unchanged.

## 5. Validation summary

- focused revised solver-free and delivery tests: `27 passed, 1 deselected`;
- full solver-free regression: `877 passed, 106 deselected`;
- focused revised nesting licensed test: `1 passed, 19 deselected`;
- full licensed regression: `106 passed, 877 deselected`;
- revised evidence replay: PASS;
- historical R3/R4 evidence replay: PASS;
- `git diff --check`: PASS.

Environment: CPython 3.12.10, Pyomo 6.10.1, gurobipy/Gurobi 13.0.2, `gurobi_direct`, Threads=1, no fallback, frozen solver numerical policy.

Scientific runs = 0; pilot runs = 0; formal experiments = 0; OOS runs = 0. Pilot remains unauthorized and unstarted.
