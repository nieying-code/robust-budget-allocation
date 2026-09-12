# Formal E3B result summary

Status: 1,800/1,800 Full Exact Certified; failures: 0.

| Cell | P1 | P2 | P3a | P3b | P4 | P5 | paid-R cases | R1 item selections | R2 item selections | mean F total | mean T-COST |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E3B_LOW_UNFAVORABLE | 32 | 8 | 0 | 0 | 160 | 0 | 0 | 0 | 0 | 1.26584e+08 | 1.21179e+09 |
| E3B_LOW_REFERENCE | 32 | 8 | 0 | 0 | 160 | 0 | 0 | 0 | 0 | 1.14584e+08 | 1.21179e+09 |
| E3B_LOW_FAVORABLE | 32 | 8 | 0 | 0 | 160 | 0 | 0 | 0 | 0 | 1.24538e+08 | 1.21179e+09 |
| E3B_MEDIUM_UNFAVORABLE | 41 | 7 | 0 | 0 | 152 | 0 | 0 | 0 | 0 | 1.54809e+08 | 1.21428e+09 |
| E3B_MEDIUM_REFERENCE | 41 | 7 | 0 | 0 | 152 | 0 | 0 | 0 | 0 | 1.42277e+08 | 1.21428e+09 |
| E3B_MEDIUM_FAVORABLE | 41 | 7 | 0 | 0 | 152 | 0 | 0 | 0 | 0 | 1.54245e+08 | 1.21428e+09 |
| E3B_HIGH_UNFAVORABLE | 50 | 8 | 0 | 0 | 142 | 0 | 17 | 17 | 0 | 1.72897e+08 | 1.21615e+09 |
| E3B_HIGH_REFERENCE | 50 | 9 | 0 | 1 | 140 | 0 | 5 | 0 | 5 | 1.57316e+08 | 1.21617e+09 |
| E3B_HIGH_FAVORABLE | 50 | 7 | 0 | 1 | 142 | 0 | 19 | 0 | 19 | 1.71742e+08 | 1.2161e+09 |

Paid reliability is absent in all Low- and Medium-risk cells. It enters only at High F-risk: 17, 5, and 19 of 200 rows under Unfavorable, Reference, and Favorable reliability economics, respectively. Favorable economics shifts the selected paid level toward R2, but adoption is nonmonotonic across the three representative reliability donors.

The evidence therefore supports conditional but not globally monotone complementarity: High disruption risk is necessary for paid-R entry in this panel, while greater reliability efficiency chiefly changes the upgrade level and yields a small net adoption increase between the extreme donor rows.

## Extreme paired interaction contrasts

| Outcome | Mean DiD | Median DiD | Increased | Unchanged | Decreased | Verdict |
|---|---:|---:|---:|---:|---:|---|
| F_total | 890441.12 | 0 | 43 | 114 | 43 | NONMONOTONIC |
| paid_R_any | 0.01 | 0 | 2 | 198 | 0 | NONMONOTONIC |
| R1_item_count | -0.085 | 0 | 0 | 183 | 17 | NEGATIVE |
| R2_item_count | 0.095 | 0 | 19 | 181 | 0 | POSITIVE |
| worst_shortage_penalty | -52418.752 | 0 | 0 | 181 | 19 | NONMONOTONIC |
| T_COST | -52418.752 | 0 | 0 | 181 | 19 | NONMONOTONIC |

All 9 cells have h09/Katrina as the worst scenario in 200/200 rows. Physical shortages remain commodity-unit specific; any raw cross-unit aggregate is descriptive only.

No resampling, representative-row reselection, parameter tuning, model change, tolerance change, or E4 run occurred.
