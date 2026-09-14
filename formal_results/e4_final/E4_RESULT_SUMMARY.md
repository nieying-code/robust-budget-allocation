# Formal E4 out-of-sample robustness

## E4-A — LOHO

- 4,800/4,800 training optimizations were Full Exact Certified and 4,800/4,800 held-out exact evaluations passed.
- Policy-label stability was 4765/4,800. All 35 label changes occurred when h09/Katrina was held out; the other 23 folds had no label transition.
- Removing h09 changed the first-stage quantities beyond the frozen numerical rule in 200/200 rows and changed the policy label in 35/200. The replacement training worst scenario was h19 in 200/200 rows.
- h09 held-out mean regret of the LOHO policy relative to the frozen full24 policy was 16674210.850496; median was 16705219.620932.
- h01, h02, and h03 produced quantity-level alternative policies without aggregate label changes; the remaining 20 non-h09 deletions were numerically first-stage stable in 200/200 rows.

The evidence distinguishes full24 worst-scenario identity from policy dependence: h09 is influential, but 165/200 policies retained their aggregate regime when it was removed.

## E4-B — Scientific OOS

- 100 frozen E1 policies were evaluated over 10 shared seeds x 2,000 frozen-generator scenarios: 2,000,000 exact recourse evaluations with zero final failures and no first-stage reoptimization.
- Across policies, OOS mean T-COST had mean 92863549.158006, median 94664109.338565, and range [73092545.183993, 103310985.664600].
- Cross-policy mean T-COST by seed ranged from 83456799.675636 to 103010731.951783; seed variation is retained rather than pooled away.
- Every policy's OOS mean T-COST was below its in-sample robust T-COST, while every policy's sampled OOS maximum was above it. This reflects the frozen stress generator's demand multipliers, not a probability calibration.
- S100 contains {"P1": 22, "P2": 2, "P3a": 1, "P4": 75}. P2 and P3a comparisons are small-sample descriptive evidence; P3b and P5 are absent from S100.
- The initial unscaled batch solve retained 60 solver-infeasible batches across six policies. All 60 had feasible original-semantic witnesses, solved optimally through an algebraically equivalent scaled retry, were mapped back, and passed original-semantic validation. No scientific input or tolerance changed.

Overall, E4 supports qualified robustness: policy regimes are highly stable to 23 of 24 single-hurricane deletions, h09 has material but not universal policy influence, and all frozen S100 policies remain exactly evaluable under independent frozen-generator demand stress. E4 does not reinterpret S100 family shares as probabilities and does not by itself re-estimate the E1-E3 interaction effects.
