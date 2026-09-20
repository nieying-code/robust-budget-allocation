# E1-Historical Scientific Diagnosis

Status: **FORMAL EXECUTION PASS / MECHANISM EVIDENCE MIXED / INDEPENDENT REVIEW REQUIRED**

## Research position

E1-Historical is the first formal component of E1. Its role is to validate the
basic Q-F-R economic mechanism under the classical historical benchmark formed by
Rawls' original 15 single-hurricane scenarios. E1-Extended remains a separate
future experiment: it will use an independently constructed, larger real
historical single-hurricane uncertainty set through 2025 to test the same
mechanism under broader empirical uncertainty. Nothing in this run performs or
claims E1-Extended, E2–E5, sensitivity analysis, or recalibration.

## Completion and identity result

The dataset audit passed with exactly `omega_01`--`omega_15` in that order. Every
row is a single-hurricane scenario with one source hurricane ID. Combined
`omega_16`--`omega_50`, no-hurricane `omega_51`, Caribbean, synthetic, and
Grass/IBTrACS data are absent. The source provides IDs `h01`--`h15` and categories
but no hurricane-name field, so no name is inferred.

The Rawls single-scenario source probabilities sum to 0.75. Conditioning on the
selected set gives `p_H(omega)=p_51(omega)/0.75`. The unchanged frozen formula
`B_ref=sum_i((cQ_i+h_i*tau)Dref_i/a_i)` then gives
`6,721,988.79033174`, versus `7,975,014.2749022` for the 51-scenario source.
The unchanged `Fbar_i=max_omega d_iomega` rule gives:

| Commodity | old 51 Fbar | Rawls-15 Fbar | difference |
| --- | ---: | ---: | ---: |
| Water | 27,000,000 | 18,000,000 | -9,000,000 |
| Seasonal Influenza Vaccine | 1,144,366.1971831 | 955,734.406438632 | -188,631.790744468 |
| Crackers | 206,878,000 | 186,200,000 | -20,678,000 |

These are mechanical dataset-derived changes, not parameter calibration.

## Formal result table

The table reports the EF representative optimum. Full method-specific decisions
remain in each raw result because the certificate protocol permits different
first-stage vectors when their objective and independent feasibility certificates
agree.

| Case | T-COST | C_Q | C_F | C_R | active Q | active F/R | worst | worst shortage penalty |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: |
| B0.90_M0 | 115,301,534.55 | 6,049,789.91 | 0 | 0 | Water 1,485,714.29; Vaccine 352,905.99 | none | omega_13 / h09 / Cat5 | 109,251,744.64 |
| B0.90_M1 | 115,301,534.55 | 6,049,789.91 | 0 | 0 | Water 1,485,714.29; Vaccine 352,905.99 | none | omega_13 / h09 / Cat5 | 109,251,744.64 |
| B0.90_M2 | 114,614,729.49 | 0 | 1,070,759.28 | 1,338,449.10 | none | Crackers F 57,125,441.55 / R2 | omega_13 / h09 / Cat5 | 108,564,939.58 |
| B1.00_M0 | 114,156,856.70 | 6,721,988.79 | 0 | 0 | Water 1,485,714.29; Vaccine 399,534.66 | none | omega_13 / h09 / Cat5 | 107,434,867.91 |
| B1.00_M1 | 114,156,856.70 | 6,721,988.79 | 0 | 0 | Water 1,485,714.29; Vaccine 399,534.66 | none | omega_13 / h09 / Cat5 | 107,434,867.91 |
| B1.00_M2 | 113,383,356.32 | 0 | 1,189,732.53 | 1,487,165.66 | none | Crackers F 63,472,712.83 / R2 | omega_13 / h09 / Cat5 | 106,661,367.53 |
| B1.10_M0 | 113,012,178.85 | 7,394,187.67 | 0 | 0 | Water 1,485,714.29; Vaccine 446,163.33 | none | omega_13 / h09 / Cat5 | 105,617,991.18 |
| B1.10_M1 | 113,012,178.85 | 7,394,187.67 | 0 | 0 | Water 1,485,714.29; Vaccine 446,163.33 | none | omega_13 / h09 / Cat5 | 105,617,991.18 |
| B1.10_M2 | 112,151,983.15 | 0 | 1,308,705.78 | 1,635,882.23 | none | Vaccine F 470,216.22 / R2 | omega_13 / h09 / Cat5 | 104,757,795.48 |

All worst-scenario budget utilizations are one within numerical tolerance. In M2,
worst-scenario exercise is 80% of the active R2 reservation, exactly matching the
Cat5 availability `1-(1-.8)*1=.8`. Complete demand, exercise `x`, shortage `u`,
and expenditure rows are in `experiments/e1_historical_rawls15/summary.json`;
all 15 scenario rows are retained in every raw case.

## A. M0 to M1

M1 is objective-equivalent to M0 at all three budgets (differences are zero within
floating-point tolerance), and F is zero for every commodity. Therefore this
experiment does **not** provide the desired evidence that basic/default R0 F has
natural standalone flexibility value under at least some tested condition.

The economic explanation is specific. The robust worst is Cat5, where R0 leaves
only 20% of a reservation available. A unit of usable worst-case service therefore
requires five reserved units, while reservation plus possible exercise competes
inside the same cash budget. At the frozen prices this bundle is dominated at the
tested budgets by Q allocation for the active robust margins. This is not a claim
that F can never have value in every possible dataset or budget; it is evidence
that M1's basic F has no value in this complete frozen E1-Historical matrix.

## B. M1 to M2

M2 improves T-COST over M1 by 686,805.06, 773,500.38, and 860,195.70 at budget
ratios 0.90, 1.00, and 1.10. Every M2 optimum uses positive F with paid R2 on the
active commodity, and every positive R expenditure is proportional to positive F.
There is no economically active paid R without F.

This supports the joint value of the F+enhanced-R bundle, but it does not isolate
R as a marginal enhancement of an F position already chosen in M1, because M1 has
no F exposure. The mechanism evidence is therefore mixed: endogenous reliability
enables valuable flexible procurement, while the default-flexibility step itself
does not activate.

The one-hot reliability variables still carry arbitrary labels on zero-F
commodities (for example EF can report R1/R2 while both F and R expenditure are
zero). These labels have no economic effect or value and are not counted as R
activation. This is a reporting/identification degeneracy of inactive variables,
not paid R without F, but it should be visible to independent reviewers.

## C. Budget response

T-COST decreases with budget for every model. M0 and M1 hold Water Q at the amount
that exactly covers the worst scenario after Cat5 Q survival and use each budget
increment for Vaccine Q. Their worst shortage penalty falls monotonically.

M2 increases the size of its R2-protected F bundle and its T-COST also falls
monotonically. EF represents the 0.90 and 1.00 optima with Crackers F and the 1.10
optimum with Vaccine F. This should not be interpreted as an identified economic
switch: A0 and A1 represent all three M2 optima with Vaccine F, and the formal
certificate explicitly accepts these different first-stage vectors because their
objectives and feasibility agree. The economic normalization produces alternative
optima. Accordingly, unweighted total shortage quantities and their probability
weighted sum can jump when the representative commodity changes; those quantities
mix gallons, doses, and 22 g servings and are descriptive rather than the objective.
The cost-weighted shortage penalty and T-COST are the appropriate economic paths.

## D. Worst-scenario structure and participation

The artificial combined Cat5 `omega_21` lock is removed because the combined rows
are absent. Nevertheless, all nine cases are locked by the genuine single Cat5
`omega_13` (`h09`). This is not automatically a failure: `omega_13` has by far the
largest single-event Crackers and Vaccine demands. In every case it is the only
scenario within 1% of the worst recourse loss. The second-ranked scenario is
`omega_06`, tens of millions of cost units below it. Thus combined-scenario
construction no longer causes the lock, but worst-case concentration remains
strong and is now attributable to a real source extreme within this dataset.

Other scenarios still have algorithmic and recourse roles. A0 starts at
`omega_01`, adds `omega_13`, and certifies after two iterations. In every A1 run,
Candidate Search adds `omega_02` and `omega_03`, Full Exact search adds
`omega_13`, and final certification evaluates all 15 scenarios. Every scenario has
a stored feasible recourse row. Hence the set is not computationally ignored, even
though only `omega_13` determines the final robust maximum.

## Old 51 versus E1-Historical

The repository's preserved old 51-scenario Formal evidence has `omega_21` as the
worst case in 9/9 cases; E1-Historical has `omega_13` in 9/9. Old and new both have
no M1 F and have F+paid-R activation in all M2 cases. The old M0/M1 representatives
use Vaccine Q only, whereas E1-Historical uses Water and Vaccine Q. Old M2 uses
Vaccine F/R2 at all budgets; E1-Historical's method-specific representatives show
the alternative-optimum pattern described above. E1-Historical T-COST is lower by
82.26--91.12 million across the matched case labels.

That comparison has an unavoidable causal limitation. The only repository result
for 51 scenarios is explicitly pre-revision historical diagnostic evidence and
uses old `eta0`, Cat4 disruption, and priority weights. E1-Historical correctly
inherits the current frozen R6-C v2 values required by this run. Therefore the
numerical deltas cannot be attributed exclusively to deleting combined and
no-hurricane scenarios. Running a new revised 51-scenario control would exceed the
authorized nine cases and was not done. The exact case-by-case comparison and this
warning are preserved in `old_51_comparison.json`.

## Independent-review issues

1. Basic/default F is inactive in all three M1 cases, so the M0-to-M1 mechanism
   evidence sought by the protocol is absent.
2. M2 supports a joint F+R2 value but cannot isolate a marginal R effect on an
   already active M1 F position.
3. `omega_13` remains a single-scenario robust lock in all nine cases; it is a real
   source extreme, not a constructed combined event, but concentration is strong.
4. Multiple optimal M2 first-stage portfolios and arbitrary inactive reliability
   labels limit commodity-level identification; objective/certificate conclusions
   remain valid.
5. The available old-51 comparison is scientifically confounded by the documented
   pre-revision parameter identity. No unauthorized control rerun was performed.

No parameter, model, algorithm, scenario, worst hurricane, budget ratio, or
activation gate was changed in response to these findings.
