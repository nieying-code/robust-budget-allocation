# Rawls24 Q-F-R availability diagnostic

This is a temporary parameter diagnostic, not a Formal E1 run or parameter
freeze. It uses the 24 real single-hurricane scenarios and the authorized
uniform `1/24` reference weights only to construct `Dref` and `B_ref`. The
robust min-max scenario set remains unweighted.

`B_ref = 26,153,247.331876762`. The three budgets are 0.75, 1.00, and 1.25
times this value. Q availability is `(0.92, 0.84, 0.76, 0.68, 0.60)` and F
availability is R0 `(0.91, 0.82, 0.73, 0.64, 0.55)`, R1
`(0.92, 0.84, 0.76, 0.68, 0.60)`, and R2
`(0.95, 0.90, 0.85, 0.80, 0.75)`. All economic parameters are inherited
unchanged from the current main baseline.

## Results

Amounts under T-COST and expenditure are monetary units. Quantity vectors are
ordered Water / Seasonal Influenza Vaccine / Crackers.

| Case | T-COST | Q quantity | F quantity | R by item | Q/F/R expenditure | Worst scenario |
|---|---:|---|---|---|---|---|
| M0 / 0.75 | 1,230,208,205.776 | 17,333,333.333 / 581,862.895 / 0 | 0 / 0 / 0 | none / none / none | 19,614,935.499 / 0 / 0 | h09 Katrina Cat5 |
| M1 / 0.75 | 1,211,937,338.948 | 0 / 0 / 0 | 1,050,000 / 2,062,775.665 / 0 | R0 / R0 / none | 0 / 5,877,134.232 / 0 | h09 Katrina Cat5 |
| M2 / 0.75 | 1,211,937,338.948 | 0 / 0 / 0 | 0 / 0 / 313,547,494.232 | none / none / R0 | 0 / 5,877,134.232 / 0 | h09 Katrina Cat5 |
| M0 / 1.00 | 1,221,598,823.802 | 17,333,333.333 / 1,035,408.389 / 0 | 0 / 0 / 0 | none / none / none | 26,153,247.332 / 0 / 0 | h09 Katrina Cat5 |
| M1 / 1.00 | 1,196,926,158.598 | 0 / 0 / 0 | 731,707.317 / 2,781,472.266 / 0 | R0 / R0 / none | 0 / 7,836,178.976 / 0 | h09 Katrina Cat5 |
| M2 / 1.00 | 1,196,926,158.598 | 0 / 0 / 0 | 18,909,090.909 / 0 / 287,382,380.467 | R0 / none / R0 | 0 / 7,836,178.976 / 0 | h09 Katrina Cat5 |
| M0 / 1.25 | 1,212,989,441.828 | 17,333,333.333 / 1,488,953.882 / 0 | 0 / 0 / 0 | none / none / none | 32,691,559.165 / 0 / 0 | h09 Katrina Cat5 |
| M1 / 1.25 | 1,181,914,978.247 | 0 / 0 / 0 | 731,707.317 / 3,485,354.396 / 0 | R0 / R0 / none | 0 / 9,795,223.720 / 0 | h09 Katrina Cat5 |
| M2 / 1.25 | 1,181,914,978.247 | 0 / 0 / 0 | 0 / 0 / 522,579,157.053 | none / none / R0 | 0 / 9,795,223.720 / 0 | h09 Katrina Cat5 |

Worst-case shortage quantities and the full-precision values are in
`summary.csv`; exact recourse diagnostics and scientific identities are in
`results.json`.

## Diagnostic reading

- M1 improves T-COST over M0 by 1.49%, 2.02%, and 2.56% as the budget rises;
  R0 F is nonzero in all three M1 cases.
- Q is completely displaced in every M1 and M2 solution. This is a strong
  structural warning, not a successful balance among Q and F.
- M2 never selects paid R1 or R2 and has the same objective as M1 at every
  budget. Different M1/M2 R0 allocations are alternative optima, not evidence
  of added reliability value.
- Katrina (h09, Cat5) is the unique exact-recourse worst scenario in all nine
  cases. This is a real single hurricane, but the diagnostic still exhibits
  complete worst-scenario concentration.
- Relative to the stated PR #23 pattern, R0 F now activates and M2 no longer
  jumps to high R. The tradeoff has moved to the opposite edge: R0 F displaces
  all Q and paid reliability has no marginal value.
- The clearest next-stage issue is the economic price balance, with the R1/R2
  uplift-versus-premium balance secondary. R0 availability itself is no longer
  the activation bottleneck. No follow-up calibration is performed here.

## Numerical note

The nine master cases use the existing full extensive-form model and frozen
Gurobi options. The separate exact-recourse diagnostic LPs retain those options
and add `NumericFocus=3`: with Rawls24's order-`1e9` RHS, h09 is falsely declared
infeasible at `FeasibilityTol=1e-9` without this scale-focused option. This is a
solver stabilization only; it changes no model, availability, economic
parameter, scenario, or decision criterion. These runs are not Formal
certification.
