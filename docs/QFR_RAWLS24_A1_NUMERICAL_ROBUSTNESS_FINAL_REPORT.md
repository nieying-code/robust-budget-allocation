# Rawls24 Layer A A1 numerical robustness repair

## Scope and guardrails

This work diagnoses and repairs numerical representation failures in the common
Q-F-R exact-result validation/oracle layer. It does not change the Q-F-R model,
Rawls24 data, B_ref, the N=1000 LHS sample table, scientific parameter ranges,
solver policy, A1 search/ranking/memory flow, convergence/stopping logic, or
scientific optimality definition. No sample was replaced and no result-driven
parameter adjustment was performed.

## Pre-fix 121-case audit

All 121 failed Rawls24 inputs were replayed without modification. The frozen
sample-table SHA-256 is
`ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0`.

Failure classification:

- restricted-master worst-loss epigraph validation: 69 cases (68 h09, 1 h05);
- exact-recourse loaded-result validation: 10 cases (h09);
- Memory exact evaluation reported infeasible: 24 cases (h19);
- Full Exact Certification incomplete: 18 cases (13 h09, 5 h17).

Observed maximum positive residuals:

| Constraint family | Maximum absolute violation | Maximum relative violation |
|---|---:|---:|
| objective epigraph | 2.384185791015625e-7 | 2.0243364415703172e-16 |
| demand/flow | 2.384185791015625e-7 | 1.948915029826923e-16 |
| budget | 3.725290298461914e-9 | 2.0529081068487494e-16 |
| fulfillment/capacity | 1.1641532182693481e-10 | 1.7623523745257671e-16 |
| nonnegativity/other | 0 | 0 |

The 42 exact LP failures had an explicit feasible witness (`x=0`, with shortage
covering residual demand) with zero scientific residual. Together with the
approximately 2e-16 relative loaded-solution residuals, this identifies
floating-point cancellation and LP scaling/presolve sensitivity rather than a
model infeasibility or parameter failure.

## Unified numerical repair

Loaded-solution validation uses family-specific scales:

`absolute violation <= 1e-7 + 1e-12 * family reference scale`

The 1e-7 absolute baseline is retained. The 1e-12 relative coefficient is over
three orders of magnitude above the observed relative residuals and remains
three orders of magnitude stricter than the frozen 1e-9 relative coefficient
used by the existing objective/convergence comparison. Objective epigraph,
budget, quantity/flow, and fulfillment/capacity each use their own dimensional
reference values. Nonnegativity and binary validation retain the prior absolute
rule.

The exact oracle first solves the unchanged production LP. If and only if this
solve fails, it retries an algebraically equivalent dimensionless Pyomo
ScaleModel clone, then propagates the solution back to the original model before
unscaled accounting, validation, and serialization. This fallback preserves the
historical numerical path for successful solves and is shared by Candidate,
Memory, and Full Exact Certification. The solver interface/options and A1 logic
are unchanged.

An intermediate always-scaled implementation certified all cases but changed
the representative first-stage optimum in 12 degenerate Q-only cases. It was
rejected by the non-regression gate. The final failure-only fallback yields zero
objective and zero first-stage differences on all 879 prior successes.

## Regression gates

- Original T1 eight cases: 8/8 A1 certified; all input hashes unchanged; all
  objectives agree with the retained A0 and EF objectives under the frozen
  tolerance. Maximum absolute A1-to-A0/EF difference is 2.9802322387695312e-8.
- Original Rawls24 failures: 121/121 A1 certified; 0 remaining failures; all
  input hashes unchanged.
- Original Rawls24 successes: 879/879 certified and non-regression PASS;
  maximum objective difference 0; maximum first-stage decision difference 0;
  policy label, selected reliability levels, and worst scenario unchanged.

## Rebuilt Rawls24 Layer A N=1000

The rebuilt run attempted the exact same 1000 samples and certified 1000/1000.
There were no failures.

- policies: P1=241, P2=0, P3a=0, P3b=0, P4=759, P5=0;
- item-level reliability labels: NONE=1920, R0=948, R1=84, R2=48;
- worst scenario: h09 (Katrina) in 1000/1000 cases;
- objective: min 1,136,111,060.572754; median 1,222,916,253.6722498;
  mean 1,218,508,854.0806003; P90 1,234,432,145.6809926;
  P95 1,237,160,704.4597526; max 1,244,166,582.4812105;
- worst total shortage: min 1,541,244,563.6636992; median
  1,827,469,533.943061; mean 1,804,900,574.82769; P90
  1,881,052,398.8986263; P95 1,881,161,083.6119013; max
  1,881,366,578.6361694;
- worst total F exercise: min 0; median 53,557,363.312026404; mean
  72,431,114.63207112; P90 173,479,112.82319406; P95
  199,610,843.50927538; max 340,712,780.40068734;
- budget usage: median/mean/P90/P95=1.0; observed range
  [0.9999999999999954, 1.0000000000000002].

A1 diagnostics:

- runtime seconds: min 0.4863202; median 0.53282035; mean 0.55116863;
  P90 0.63197385; P95 0.64451755; P99 0.67151128; max 0.698125;
- iterations: min/median 3; mean 3.75; P90 6; P95/P99/max 7;
- memory opportunities=1000, memory hits=0;
- candidate hits=1750, candidate scenarios planned=3750;
- Full Exact Certification calls=2000, complete calls=2000;
- scenario evaluations=53,750.

Relative to the pre-fix partial run, certification changes from 879/1000 to
1000/1000. The 879 already-successful scientific solutions are unchanged; the
policy-count increment contributed by the recovered 121 cases is P1 +12 and P4
+109. The repaired full run remains scientific evidence that h09 locks the worst
scenario across this sampled parameter space; the numerical repair does not
alter or conceal that result.

## Evidence locations

- pre-fix audit: `simulation_results/qfr_mechanism_layer_a_rawls24_numerical_audit_pre_fix/`
- final 121 replay: `simulation_results/qfr_mechanism_layer_a_rawls24_121_replay_final_fallback/`
- final 879 non-regression: `simulation_results/qfr_mechanism_layer_a_rawls24_879_nonregression_final_fallback/`
- original T1 eight-case regression: `simulation_results/qfr_mechanism_layer_a_t1_8case_regression_post_scale_fix/`
- rebuilt N=1000: `simulation_results/qfr_mechanism_layer_a_rawls24_n1000_post_numerical_fix/`

