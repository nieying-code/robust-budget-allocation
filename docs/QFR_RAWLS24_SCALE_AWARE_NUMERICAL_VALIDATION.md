# Rawls24 scale-aware Q-F-R numerical validation

## Audit basis

The frozen pre-fix replay contains all 121 Rawls24 failures. The largest observed
worst-loss epigraph and demand-flow residual is 2.384185791015625e-7 against
reference magnitudes near 1e9, or approximately 2e-16 relative error. The largest
budget and fulfillment residuals are 3.725290298461914e-9 and
1.1641532182693481e-10. Forty-two exact-recourse LPs reported infeasible even though
an explicit x=0, shortage=demand-available-Q witness satisfies every scientific
constraint; their rows span h09, h17, and h19.

This pattern is consistent with floating-point cancellation and badly scaled LP rows,
not a model feasibility or scientific-parameter failure.

## Validation rule

Loaded-solution feasibility uses:

`threshold = 1e-7 + 1e-12 * max(1, family-specific reference magnitudes)`

The absolute term retains the prior implementation baseline. The 1e-12 relative term
is more than three orders of magnitude above the observed approximately 2e-16 relative
residue while remaining three orders of magnitude stricter than the frozen R3
objective/convergence comparison coefficient of 1e-9.

Reference magnitudes are never shared indiscriminately across constraint families:

- objective epigraph: theta and the applicable scenario loss;
- scenario budget: B, first-stage expenditure, and exercise expenditure;
- demand flow: applicable demand, available Q, exercise, and shortage quantities;
- F fulfillment/capacity: exercise, fulfillable F, F, and the applicable capacity;
- nonnegativity/binary restrictions: the prior absolute check remains in force.

The rule validates floating-point representations only. It does not participate in
A1 stopping, gap, violation, candidate ranking, memory, or certification logic.

## Exact-recourse row scaling

The exact-recourse LP divides each demand row by its demand-flow scale, each
fulfillment row by its own fulfillable-F scale, and the cash row by B. These are algebraically
equivalent positive row scalings. Objective coefficients, variables, feasible set,
scientific accounting, and serialized quantities remain unchanged. Candidate,
Memory, and Full Exact Certification all call this same exact-recourse implementation.
