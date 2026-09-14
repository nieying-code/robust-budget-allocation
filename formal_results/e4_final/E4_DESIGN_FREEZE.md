# Formal E4 design freeze

## E4-A — Historical LOHO

- Rawls24 h01-h24; one event is held out and the remaining 23 form the training uncertainty set.
- Frozen S200: `2b7d7a92c9a0301203a6b73a349a32903b83434038dc88a52fe1cc734ffad32d`.
- 24 x 200 = 4,800 M2 training optimizations.
- Absolute budget remains `19137905.85543848`; B_ref and F capacity are not recomputed.
- Training uses `A1_FINAL_NO_MEMORY_V1` / `A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY`.
- The trained first-stage policy is fixed for exact held-out recourse evaluation.
- Frozen E1 Q/F/R/z scientific fields are the evaluation policy source. The promoted evidence retains the historical execution-object hash as provenance but omits inactive-level floating residues, so E4 records both that source hash and a deterministic data-independent canonical policy hash; scientific equality is validated from Q/F/R/z, policy label, reliability labels, and first-stage cost under the frozen validation rule.

## E4-B — Scientific OOS

- Frozen S100: `1ad7dcbf17a2339a41723bea60ad0e7e8fce70017d54c5c1f80ba7412accd0ee`; policies come from frozen E1 and are not reoptimized.
- Generator: `RAWLS24_SCIENTIFIC_OOS_GENERATOR_V1` / `d39afab714dc68392db574f6efebfe0176de169b571db0a4eb471cd45afe8340`.
- Seeds: 20260904, 20260905, 20260906, 20260907, 20260908, 20260909, 20260910, 20260911, 20260912, 20260913; 2,000 scenarios per seed, shared by all policies.
- Draw order: template, common multiplier, Water, Vaccine, Crackers.
- No no-hurricane event and no extra availability noise.
- The stress bands are design perturbations, not estimated real-world probabilities.
- Batch evaluation is the separable sum of 2,000 independent original exact-recourse LPs; every returned solution is checked against original Q-F-R recourse semantics.
- Compact evidence stores frozen generator tables, policy x seed summaries, and a canonical hash of all scenario-level evaluated results. The two million rows are deterministically reconstructible and are not duplicated in the repository.

Physical shortage is interpreted within each commodity's service unit. Raw cross-unit totals and the frozen service-level ratio are descriptive only; valued shortage and T-COST carry cross-commodity economic meaning.
