# Formal E4-B scientific OOS result summary

- Frozen policies: 100; seeds: 10; scenarios per seed: 2,000.
- Fixed-policy exact recourse evaluations: 2,000,000, grouped into 1,000 separable exact batches; final failures: 0.
- Initial batch solve: 60 solver-infeasible batches across 6 policies. All were retained, witness-gated, solved optimally by the algebraically equivalent scaled retry, mapped back, and passed original-semantic validation.
- Policy-family counts in deterministic S100: {"P1": 22, "P2": 2, "P3a": 1, "P4": 75}. These are not real-world probabilities.
- Generator: `RAWLS24_SCIENTIFIC_OOS_GENERATOR_V1` / `d39afab714dc68392db574f6efebfe0176de169b571db0a4eb471cd45afe8340`.

All OOS scenarios are shared across policies within seed. Q/F/R are frozen E1 decisions and are never reoptimized. Physical shortages are compared within commodity units; valued shortage and T-COST support cross-commodity interpretation.
