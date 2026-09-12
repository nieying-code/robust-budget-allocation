# Formal E2-C Reliability Sensitivity / Boundary Analysis

E2-C is a solver-free descriptive analysis of the frozen Final E1 population.
It performs no new scientific optimization, resampling, parameter adjustment,
or outcome-driven threshold selection.  Final E1, E2-A, and E2-B artifacts are
read-only inputs whose hash inventories are recorded before and after the build.

## Population and measures

Aggregate F-active means `sum_i(F_i) > 1e-7`.  The frozen population contains
792 F-active and 208 F-inactive rows.  Commodity-level boundary analysis uses
the 1,160 active item observations: 1,023 R0, 86 R1, and 51 R2.  NONE is retained
separately for the 1,840 inactive item observations.  No paid reliability level
occurs without protected F.

The frozen ratios define `A_R1 = eta_1/(c_R1/c_Q)` and
`A_R2 = (eta_2-eta_1)/((c_R2-c_R1)/c_Q)`.  The descriptive supply-risk score is
`S_F = mean_k(1-rho_Fk)`, and F exposure is fixed before inspecting outcomes as
`F_i*S_F`.  These quantities do not alter the model.

## Main evidence

R0 has median A_R1 1.568 (IQR 0.934–2.583), whereas R1+R2 has median 4.009
(IQR 2.204–7.802).  The rank-biserial effect is 0.512; the 24.4% ordering
violation rate and overlapping IQRs show that A_R1 is informative but not a
separating structural threshold.  In fixed A_R1 quintiles, R1 share rises from
0% in the first quintile to 30.9% in the fifth.

R1 has median A_R2 0.909 (IQR 0.564–1.366), while R2 has median 4.606
(IQR 3.720–7.945).  The IQRs do not overlap; rank-biserial effect is 0.972 and
the ordering violation rate is 1.4%.  R2 share is 0% in the first two fixed
A_R2 quintiles and 16.4% in the fifth.  These remain empirical boundaries, not
structural theorems.

F exposure does not show a simple amplification ordering.  Its rank-biserial
effect is -0.177 for R0 versus R1+ and 0.057 for R1 versus R2.  The fixed 5x5
efficiency-by-exposure maps likewise show substantial overlap and no monotone
exposure gradient.  Physical F quantities differ sharply by commodity, so
exposure alone cannot explain paid-R choice across archetypes.

Vaccine selects paid R in 67/225 active observations, compared with 13/356 for
Water and 57/579 for Crackers.  Commodity-specific A_R1 rank-biserial effects
for R0 versus R1+ are 0.263, 0.617, and 0.419 respectively.  A_R2 strongly
orders R1 versus R2 within all commodities (1.000, 0.968, and 0.995), although
Water has only five R1 and eight R2 observations.  The different entry rates
despite common parameter ratios demonstrate that the boundary is conditioned
by commodity allocation, costs, and heterogeneity rather than a universal
ratio alone.

Frozen E2-B is supplementary evidence only: paid-R item totals decline
143→137→134 over B075→B100→B125.  Combined with full budget utilization at all
levels, this does not support a mechanical budget-driven interpretation.
Overall, `RELIABILITY_IS_VALUE_DRIVEN = QUALIFIED`: efficiency ratios—especially
incremental A_R2—have meaningful explanatory value, but commodity context,
supply-risk severity, and portfolio substitution prevent a universal
one-dimensional boundary.

Rebuild and verify with the existing project interpreter:

```powershell
.venv/Scripts/python.exe scripts/run_formal_e2c.py build
.venv/Scripts/python.exe scripts/run_formal_e2c.py verify
```
