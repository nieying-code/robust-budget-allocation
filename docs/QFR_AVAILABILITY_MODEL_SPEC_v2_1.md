# Q-F-R Availability Model Specification v2.1

Status: **FROZEN SCIENTIFIC/MATHEMATICAL AMENDMENT; IMPLEMENTATION AND CORRECTNESS PENDING**

This specification is read together with the frozen pre-revision `MODEL_SPEC_v2.md`. Every equation and boundary not expressly amended below remains unchanged. The old file and its evidence are retained and are not rewritten.

## 1. Revised scenario realization

The finite uncertainty realization is

`U = {(d_omega, rho_Q_omega, delta_omega): omega in Omega}`,

where each realization has complete item-indexed values:

- `d[i,omega] >= 0`;
- `0 <= rho_Q[i,omega] <= 1`;
- `0 <= delta[i,omega] <= 1`.

All three maps must cover exactly every declared `(omega,i)` pair, contain finite non-NaN values, and participate in complete data and scenario identities. The pilot baseline repeats its scenario-level Q availability and disruption values for every item; the production schema remains item-specific.

`a_i` remains normal-storage retention with `0<a_i<=1`. It is neither replaced by nor merged with `rho_Q[i,omega]`.

## 2. Q availability and demand satisfaction

Define scenario-effective prepositioned inventory as

`Q_eff[i,omega] = a_i * rho_Q[i,omega] * Q_i`.

Demand satisfaction becomes:

- M0: `a_i*rho_Q[i,omega]*Q_i + u[i,omega] >= d[i,omega]`;
- M1/M2: `a_i*rho_Q[i,omega]*Q_i + x[i,omega] + u[i,omega] >= d[i,omega]`.

Q procurement/storage cost remains `sum_i (c_Q[i]+h_i*tau)Q_i`. Q availability changes physical service in a scenario; it does not refund cash, change the first-stage cost, or create a new budget.

## 3. Revised reliability levels

For every item the ordered levels remain `{0,1,2}`, with:

`0 <= eta[i,0] < eta[i,1] < eta[i,2] < 1`.

The zero boundary is valid in the general model: under full disruption, base F may then be completely unavailable. This does not remove level 0 or change the fulfillment equation. The frozen pilot baseline remains `(0.20,0.50,0.80)` for every item. Reliability premiums retain:

`c_R[i,0]=0 < c_R[i,1] < c_R[i,2]`.

Flexible fulfillment remains linear:

`rho_F[i,omega,r] = 1-(1-eta[i,r])*delta[i,omega]`,

`x[i,omega] <= sum_r rho_F[i,omega,r]*F[i,r]`.

Level 0 is inherent base fulfillment, not a paid R enhancement. M1 permits only level 0 and has no positive R cost. M2 permits all three levels. Therefore `M2 | levels={0} = M1`, while `M1 | F=0 = M0` continues to hold under the same scenario-specific Q availability.

## 4. Unchanged cash and objective accounting

For every scenario:

`C_Q + C_F + C_R + sum_i p_F[i]*x[i,omega] <= B`.

Shortage loss `sum_i s_i*u[i,omega]` remains outside the cash budget and inside scenario loss. The objective remains first-stage real spending plus the worst scenario's exercise spending and shortage penalty. No additional budget, timing stage, salvage, disposal, or scenario probability is added.

## 5. Frozen pilot configuration formulas

The pilot configuration is constructed—not executed—from the exact inputs in `QFR_AVAILABILITY_RESEARCH_REVISION_v2_1.md`:

- Vaccine computational storage rate: `h=0.08/6`; `tau=6`.
- `c_F[i]=0.20*c_Q[i]`.
- `p_F[i]=0.85*c_Q[i]`.
- `c_R[i]=(0,0.10*c_Q[i],0.25*c_Q[i])`.
- `s_i=4*c_Q[i]`.
- `Fbar_i=max_omega d[i,omega]` over exactly omega_1 through omega_5.
- `B_ref=sum_i(c_Q[i]+h_i*tau)*d_nominal[i]/a_i=306313.545054945 USD` within ordinary floating-point representation.
- Budgets are computed as `ratio*B_ref` for ratios 0.90, 1.00, and 1.10; rounded display values are not computational inputs.

## 6. Implementation and validation contract

The revised schema must reject missing, extra, nonfinite, or out-of-domain Q-availability entries. `rho_Q` must be included in canonical serialization, `data_sha256`, and `scenario_sha256`. Loaded-model, accounting, exact-recourse, certificate, and replay validation must therefore bind to it through the existing complete data identities.

Independent checks must recompute scenario-specific effective Q, demand feasibility, F fulfillment, fixed-budget feasibility, shortage loss, objective, and maximum violation. No parallel evidence/security framework is authorized.
