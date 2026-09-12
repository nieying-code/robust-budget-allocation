# Formal E3A result summary

Status: 1,800/1,800 Full Exact Certified; failures: 0.

| Cell | P1 | P2 | P3a | P3b | P4 | P5 | Vaccine Q-active | Vaccine F-active | Vaccine paid-R | mean Vaccine Q | mean Vaccine F | mean T-COST |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E3A_H000_MF080 | 0 | 0 | 0 | 0 | 200 | 0 | 0 | 56 | 27 | 0 | 547876 | 1.19824e+09 |
| E3A_H000_MF100 | 5 | 0 | 0 | 0 | 195 | 0 | 5 | 49 | 31 | 17539.6 | 378362 | 1.21349e+09 |
| E3A_H000_MF120 | 32 | 0 | 0 | 0 | 168 | 0 | 32 | 56 | 37 | 150389 | 321823 | 1.22299e+09 |
| E3A_H050_MF080 | 0 | 0 | 0 | 0 | 200 | 0 | 0 | 54 | 29 | 0 | 540011 | 1.19824e+09 |
| E3A_H050_MF100 | 2 | 3 | 0 | 0 | 195 | 0 | 2 | 44 | 30 | 6916.82 | 348278 | 1.21351e+09 |
| E3A_H050_MF120 | 24 | 7 | 1 | 0 | 168 | 0 | 24 | 55 | 37 | 78966.5 | 317854 | 1.22313e+09 |
| E3A_H100_MF080 | 0 | 0 | 0 | 0 | 200 | 0 | 0 | 53 | 27 | 0 | 532690 | 1.19824e+09 |
| E3A_H100_MF100 | 1 | 4 | 0 | 0 | 195 | 0 | 1 | 48 | 30 | 3365.8 | 381714 | 1.21352e+09 |
| E3A_H100_MF120 | 18 | 11 | 2 | 1 | 168 | 0 | 18 | 58 | 38 | 56946.3 | 336321 | 1.22322e+09 |

The preservation main effect is conditional on F economics. With favorable F economics (mF=.8), Vaccine Q is already zero in all 200 rows and increasing preservation burden produces no Q-to-F regime shift. At mF=1.0 and 1.2, higher preservation burden reduces mean Vaccine Q; the corresponding F response is nonmonotonic and most rows retain their regime.

The extreme paired difference-in-differences is negative for Vaccine Q, positive but heterogeneous for Vaccine F, and small/nonmonotonic for paid R. Thus the interaction is clearest in allocation intensity and sparse regime transitions, not a uniform Q-to-F switch.

## Extreme paired interaction contrasts

| Outcome | Mean DiD | Median DiD | Increased | Unchanged | Decreased | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Q_Vaccine | -93442.246 | 0 | 0 | 168 | 32 | NEGATIVE |
| F_Vaccine | 29684.046 | 0 | 20 | 164 | 16 | NONMONOTONIC |
| paid_R_Vaccine | 0.005 | 0 | 3 | 195 | 2 | NONMONOTONIC |
| worst_shortage_Vaccine | 39675.94 | 0 | 48 | 137 | 15 | NONMONOTONIC |
| T_COST | 224511.1 | 0 | 32 | 168 | 0 | POSITIVE |

All 9 cells have h09/Katrina as the worst scenario in 200/200 rows. Physical shortages remain commodity-unit specific; any raw cross-unit aggregate is descriptive only.

No resampling, representative-row reselection, parameter tuning, model change, tolerance change, or E4 run occurred.
