# R6-C Scientific Revision / Re-freeze v2

Status: `RE-FREEZE CANDIDATE / INDEPENDENT REVIEW REQUIRED / R7 NOT AUTHORIZED`

## 1. Stage identity and reason for return

R6-C remains part of R6, the Formal experiment design/data/matrix freeze stage. It is not R8 and does not report revised experimental results. The old R7-E1 execution and engineering certification passed, but its results exposed a scientific-mechanism problem in the old Formal baseline. Governance therefore returned from old R7-E1 to R6 for a justified scientific revision and a new identity-bound freeze.

The permitted sequence is: old R6 freeze → old R7-E1 → scientific diagnosis → R6-C re-freeze → independent review → revised R7-E1 → independent scientific review → E2–E5. Formal scientific runs in R6-C are zero.

## 2. Historical evidence boundary

The complete `experiments/r7_e1/` directory is retained byte-for-byte as **PRE-REVISION HISTORICAL DIAGNOSTIC EVIDENCE**. Its execution/certification status remains PASS. It is not a revised E1 result and cannot authorize E2–E5.

The historical diagnosis was:

1. M0 and M1 objectives were approximately equal; M1 did not activate F at any of the three budgets.
2. M0/M1 positive first-stage allocation was Vaccine Q only.
3. M2 selected Vaccine F with paid R2 at all budgets, with Q=0.
4. Water and Crackers had no positive Q/F; no commodity used a Q/F mix.
5. All nine robust-cost worst scenarios were `omega_21` (`h10+h09`, Cat5, rhoQ=.70, delta=1).
6. Old eta0=0 made M1 base-F availability zero whenever delta=1; old Cat4 and Cat5 both used delta=1.
7. Old lambda `(1.5,2.5,1)` further emphasized Vaccine shortage exposure.

These observations justify revising the design; they are not targets for activation tuning. R6-C did not run revised E1 before choosing parameters and does not require M1 F, M2 paid R, all-commodity allocation, Q/F mixing, or a changed worst scenario.

## 3. Revised Formal baseline (P1–P10)

### P1 Commodities

| Commodity | Service unit | Effective Q economics / retention | Demand mapping |
| --- | --- | --- | --- |
| Water | 1 gallon | cQ=.6477 USD/SU; h·tau=0; a=1 | `1000 × Rawls Water` |
| Seasonal Influenza Vaccine | 1 dose | purchase=13.916; six-month cold-chain=.50; effective Q cost=14.416; a=1 | `(140/13.916) × Rawls Medical` |
| Crackers | 22 g | cQ=.09372 from `4.26 USD/kg × 22/1000`; h=0; a=.90 | `14 × 1000 × Rawls MRE` |

The Vaccine demand mapping is an economic-scale normalization proxy, not medical, physical, or clinical equivalence. For Crackers, `×1000` converts the Rawls MRE unit and `×14` is an energy-service normalization factor, not physical equivalence. Crackers a=.90 is storage-adjusted effective service retention, not an observed 10% physical mass loss.

### P2–P4 Scenarios, rhoQ, and delta

The 51 original-probability Rawls Gulf Coast scenarios remain: 15 single-hurricane, 35 two-hurricane, and one no-hurricane. Combined severity is the maximum constituent category. No-hurricane always has d=0, rhoQ=1, delta=0.

| Category | Cat1 | Cat2 | Cat3 | Cat4 | Cat5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| rhoQ | .90 | .85 | .80 | .75 | .70 |
| delta | .10 | .30 | .60 | .80 | 1.00 |

rhoQ is a Pilot-anchored research-design mapping, not an empirical Saffir–Simpson inventory-loss estimate. Delta is a literature-bounded severity calibration: Cat4 is severe partial disruption and Cat5 is the extreme full-disruption boundary; these are not empirical Saffir–Simpson damage estimates.

### P5–P8 Reliability and costs

Eta is revised to `(.20,.50,.80)`. R0 is the basic/built-in mitigation capability of reserved F, has zero premium, and is not a paid reliability enhancement. M1 can use F only at R0. M2 can select R0/R1/R2; R1/R2 are paid enhancements. These are Pilot-anchored calibrated tiers, not empirical reliability estimates.

Reservation/exercise ratios remain phi=.20 and psi=.85. Reliability premium ratios remain `(0,.10,.25)cQ`. Beta remains 4. Lambda is revised from `(1.5,2.5,1)` to the neutral `(1,1,1)` baseline, so `s_i=beta·lambda_i·cQ_i`.

### P9–P10 Capacity and budget

`Fbar_i=max_omega d_iomega` is derived from the revised 51-scenario data. Formal budgets are `.90/1.00/1.10 B_ref`. `B_ref=sum_i((cQ_i+h_i tau)Dref_i/a_i)` is deterministically regenerated under the new freeze. Its numerical value remains `7,975,014.2749022` USD, while its revised data/config identities are new.

## 4. Provenance classifications

Rawls scenarios/probabilities/Water are source-based public case data. Vaccine cQ=13.916 is a CDC official price; the 2–8°C requirement is FDA/CDC official guidance. The .50 six-month cold-chain amount is a literature-informed/literature-bounded research-design calibration, not an exact observed seasonal-influenza storage cost. Crackers 22 g is a USDA official serving definition, and .09372 is a source-based reconstructed price. Crackers retention combines a literature-supported storage-deterioration mechanism with calibrated effective-service retention.

rhoQ, delta, eta, phi/psi, reliability premiums, and beta retain their explicit research-design/calibration classifications. Mechanism literature does not make their exact values empirical estimates. Lambda `(1,1,1)` is the neutral Formal baseline.

## 5. Unchanged scientific model and algorithm boundary

M0=Q, M1=Q+F with R0 only, and M2=Q+F+R are unchanged. Q/F/R remain first-stage decisions; x/u remain second-stage. The unified budget, T-COST objective, shortage accounting, F exercise, R timing, A0/A1 definitions, certificate semantics, solver policy, tolerance policy, and exact availability equation `1-(1-eta_r)delta` are unchanged.

## 6. Revised E1–E5 matrix

### E1 — Main experiment

E1 has 3 models × 3 budgets = 9 cases. Frozen outputs include T-COST/objective, Q, F, selected R, second-stage x, shortage u, budget usage, robust-cost worst scenario, and F utilization. F utilization separately reports available/fulfillable F capacity and actually exercised F.

Correctness, identity, certificates, and execution integrity are hard gates. Optimizer activation patterns are scientific results, not gates.

### E2 — One-factor sensitivity

All cases use M2 at B_ref and hold non-varied parameters at the revised baseline.

1. Vaccine cold-chain: `.25/.50/1.00` USD/dose.
2. Crackers retention: `.80/.90/1.00`; a=1 switches the storage-loss mechanism off.
3. F price split: `(.10,.95)/(.20,.85)/(.30,.75)`, each summing to 1.05.
4. Positive R premium multiplier gamma_R: `.5/1/1.5`; R0 remains zero.
5. Eta Low/Base/High: `(.10,.40,.70)/(.20,.50,.80)/(.30,.60,.90)`.
6. Delta gamma: `.8/1/1.2`, producing `(.08,.24,.48,.64,.80)`, `(.10,.30,.60,.80,1)`, and `(.12,.36,.72,.96,1)`; no-hurricane delta remains zero.
7. Beta: `2/4/6`.
8. Lambda: neutral plus symmetric Water, Vaccine, and Crackers shocks at 1.25 and 1.50: seven configurations total. The old `(1.5,2.5,1)` is excluded.

E2 has 28 logical memberships and 21 unique physical configurations. Its eight baseline memberships point to one physical identity, so baseline deduplication removes seven duplicate solves.

### E3 — Interactions

E3-I1 is Vaccine cold-chain × F price split, 3×3. E3-I2 is delta gamma `.8/1/1.2` × R premium gamma `.5/1/1.5`, 3×3. There are 18 logical cells and 17 unique physical configurations within E3 because the two center points share the revised baseline identity. Matching E2 OFAT edge/center configurations reuse their physical identities; E3 contributes eight new physical configurations beyond E2.

### E4 — Out-of-sample robustness

Historical evaluation is 15-hurricane LOHO. Synthetic evaluation uses 10 registered seeds × 2000 scenarios. Training produces fixed Q/F/R; test evaluation reoptimizes only x/u. The revised rhoQ, delta, eta, lambda and scenario rules bind both generator and evaluator. Synthetic no-hurricane draws force d=0, rhoQ=1, delta=0 and do not invent no-hurricane demand/loss.

### E5 — Algorithm experiment

Algorithms are A0, A1_no_memory, and A1_full on the E1 nine-case set, with three timing repetitions per algorithm/case: `3×9×3=81` planned timed runs. Actual R6-C timing runs are zero.

## 7. Identities and execution seal

The authoritative machine artifacts are:

- `configs/r6c_scientific_revision_v2.json`
- `configs/r6c_formal_ready_data_v2.json`
- `configs/r6c_formal_experiment_matrix_v2.json`
- `configs/r6c_formal_experiment_matrix_expanded_v2.json`
- `docs/R6_C_DELIVERY_MANIFEST.json`
- `docs/R6_C_HASHES.sha256`

Old Formal identities remain historical and cannot be substituted for these revised identities. The expanded matrix records zero executions for E1–E5. No revised Formal case, OOS policy evaluation, or timing experiment was run.

## 8. Gate

The only next step is independent review of R6-C. Revised R7-E1 remains prohibited until that review passes and the user authorizes the transition. E2–E5 remain prohibited until revised E1 and its independent scientific review pass.
