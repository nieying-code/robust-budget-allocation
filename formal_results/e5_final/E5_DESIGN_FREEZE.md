# Formal E5 design freeze — E5-A execution stage

- Dataset: Rawls24; items: Water, Seasonal Influenza Vaccine, Crackers.
- Frozen subset: S200 `2b7d7a92c9a0301203a6b73a349a32903b83434038dc88a52fe1cc734ffad32d`.
- Algorithms: production A0 and `A1_FINAL_NO_MEMORY_V1` (`A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY`).
- Timing: three repetitions per algorithm-instance; wall clock surrounds only the solver call.
- Order: paired and interleaved; `(S200 position + repetition)` even runs A0 then A1, odd runs A1 then A0.
- Runtime unit: seconds. Per-instance comparison uses the median of three repetitions.
- No post-hoc tie band: strict measured ordering is reported.
- Correctness precedes runtime interpretation. E5-A cannot support a scalability claim.
- E5-A completed and is frozen at 1,200/1,200 certified timed runs.
- E5-B completed under the frozen scenario-scalability design at 720/720 certified timed runs.
- E5-C runs: 0.
