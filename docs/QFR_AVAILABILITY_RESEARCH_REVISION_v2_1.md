# Q-F-R Availability Research Revision v2.1

Status: **SCIENTIFIC REVISION FROZEN BY EXPLICIT USER DECISION; PILOT NOT STARTED**

This document amends, but does not overwrite, the R0–R4 Q-F-R v2 scientific history. The original `RESEARCH_DESIGN_v2.md`, `MODEL_SPEC_v2.md`, R3/R4 protocols, implementations, and evidence remain the authoritative provenance for the pre-revision model. From this revision onward, the scientific model is the original fixed-budget, heterogeneous-material, two-stage Q-F-R design as amended here and specified mathematically in `QFR_AVAILABILITY_MODEL_SPEC_v2_1.md`.

## 1. Unchanged structure

- Q is pre-disaster physical prepositioning.
- F is pre-disaster reservation of flexible post-disaster supply or production capacity.
- R is the pre-disaster reliability level attached only to F fulfillment.
- Q, F, and R are first-stage decisions; only exercise `x` and shortage `u` are second-stage decisions.
- `M0=Q`, `M1=Q+F`, and `M2=Q+F+R` remain nested.
- The single fixed total budget, objective accounting, shortage accounting, representative channel, heterogeneous multi-item structure, and finite-scenario robust framework are unchanged.

No dynamic perishability, supplier dimension, cross-item substitution, second emergency budget, DRO, OOS execution, pilot execution, or new algorithm mechanism is introduced.

## 2. Scientific amendment: Q is scenario-available

Normal storage retention and disaster-time availability are distinct:

`a_i` is the fraction retained through normal storage; `rho_Q[i,omega]` is the fraction of that retained stock available in disaster scenario `omega`. The Q contribution to demand satisfaction is therefore

`a_i * rho_Q[i,omega] * Q_i`.

The production domain is `0 <= rho_Q[i,omega] <= 1`. Complete unavailability is allowed by the general schema, although the frozen pilot baseline contains no zero-Q-availability scenario.

The general schema remains item-specific for both `rho_Q[i,omega]` and `delta[i,omega]`. In the pilot baseline only, the same scenario value is copied to Sugar, Measles Vaccine, and Rice; no commodity-specific pilot disruption is permitted.

## 3. Revised F base fulfillment

Flexible fulfillment remains

`rho_F[i,omega,r] = 1 - (1-eta[i,r]) * delta[i,omega]`,

but the base level now has positive inherent fulfillment:

`eta[0]=0.20 < eta[1]=0.50 < eta[2]=0.80 < 1`.

Level 0 has zero reliability premium and represents F without paid reliability enhancement. Thus M1 remains Q+F, and restricting M2 to level 0 yields M1. R raises F fulfillment above this base; it does not determine whether F exists and never protects Q.

## 4. Frozen pilot-baseline inputs (configuration only)

The three items are Sugar, Measles Vaccine, and Rice. Nominal demands are 67,000, 9,380, and 67,000 SU. Q procurement costs are 0.55, 0.39, and 3.60 USD/SU. Retention is 1, 1, and 0.91. The horizon is six months. Sugar and Rice storage cost is zero. Vaccine preservation is frozen as `h*tau=0.08 USD/SU`, with computational input `h=0.08/6`; `0.0133` is display-only.

For every item, `c_F=0.20*c_Q`, `p_F=0.85*c_Q`, and shortage penalty `s=4*c_Q`. Reliability premiums are `0`, `0.10*c_Q`, and `0.25*c_Q` for levels 0, 1, and 2. Maximum nominal flexible capacity is `Fbar_i=max_omega d[i,omega]` over exactly the five frozen pilot scenarios.

| Scenario | Demand multiplier | Q availability | delta |
| --- | ---: | ---: | ---: |
| omega_1 | 0.80 | 1.00 | 0.0 |
| omega_2 | 1.00 | 1.00 | 0.0 |
| omega_3 | 1.00 | 0.85 | 0.5 |
| omega_4 | 1.20 | 0.85 | 0.5 |
| omega_5 | 1.00 | 0.70 | 1.0 |

The implied availability table is:

| State | Q | F+R0 | F+R1 | F+R2 |
| --- | ---: | ---: | ---: | ---: |
| normal | 1.00 | 1.00 | 1.00 | 1.00 |
| medium | 0.85 | 0.60 | 0.75 | 0.90 |
| severe | 0.70 | 0.20 | 0.50 | 0.80 |

The reference budget is the cost of Q alone meeting nominal demand in the normal-availability state:

`B_ref = sum_i (c_Q[i] + h[i]*tau) * d_nominal[i] / a[i]`

and equals `306313.545054945 USD` under the frozen inputs (`306313.55 USD` for display). Pilot budget ratios are 0.90, 1.00, and 1.10. Configurations may compute these values, but this revision task does not execute the pilot.

## 5. Correctness and algorithm boundary

EF, A0 Standard C&CG, and the existing A1 state machine are adapted only through the shared revised data/model/recourse semantics. Memory, Candidate Search, exact certification, convergence, deterministic rules, solver policy, and algorithm names do not change.

The pre-revision R3/R4 correctness evidence proves only the pre-revision model. Before pilot authorization, revised M0/M1/M2 must independently re-establish EF/A0/A1 agreement using the unchanged registered numerical tolerance and solver policy. Correctness runs are not pilot or scientific experiments.
