# Formal E2-A result summary

The four frozen OFAT cells account for all 4,000 requested parameter-row/case
pairs. Final E1 contributes 1,000 reused baseline rows and was not rerun.

Certification is incomplete: 3,795 rows passed Full Exact Certification and
205 rows retained `oracle_failure` status (H0 52, H1 55, A100 45, A080 53).
No row was dropped, replaced, or resampled. A serial diagnostic replay of
`E2A_VACCINE_H0/LA-0002` localized its failure to an h09 exact-recourse solve
reported infeasible during Full Exact Certification at the tight cash-budget
boundary. This diagnostic does not establish that all 205 failures have the
same detailed cause; resolving them requires separate engineering review.

Certified-row policy counts are:

| Case | P1 | P2 | P3a | P3b | P4 | P5 | Certified |
|---|---:|---:|---:|---:|---:|---:|---:|
| Vaccine hτ=0.00 | 241 | 0 | 0 | 0 | 707 | 0 | 948 |
| Vaccine hτ=1.00 | 173 | 53 | 8 | 7 | 704 | 0 | 945 |
| Crackers a=1.00 | 241 | 0 | 0 | 0 | 714 | 0 | 955 |
| Crackers a=0.80 | 208 | 26 | 4 | 3 | 706 | 0 | 947 |

On certified pairs, removing Vaccine storage burden changed all 33 mixed
baseline policies to P1 and activated Vaccine Q in 241 rows. Raising the burden
to 1.00 produced 35 P1-to-mixed transitions (27 P2, 4 P3a, 4 P3b) and reduced
Vaccine Q activity to 173 rows. Setting Crackers retention to 1.00 activated
Crackers Q in 241 certified rows and changed the 33 mixed baseline policies to
P1. Lowering retention to 0.80 left aggregate policy labels unchanged among
the 947 certified pairs; quantity reallocations can still occur within labels.

Median paired T-COST change is zero in every cell. Mean certified-pair change
is -187,893.82 (Vaccine hτ=0), +152,346.10 (Vaccine hτ=1), -186,516.59
(Crackers a=1), and approximately zero (Crackers a=0.8). These summaries are
conditional on certification and must not be treated as complete-population
E2-A estimates until the 205 failures are independently resolved.

h09/Katrina is the worst scenario for every certified row in all four cells.
E2-B, E2-C, and E2-D scientific runs remain zero.
