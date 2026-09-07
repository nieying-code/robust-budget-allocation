# Layer A T2 numerical repair and Rawls24 construction audit

## Scope

T2 applies one numerical-feasibility repair, verifies the eight frozen T1 inputs, and
constructs a separate Rawls24 Layer A simulation. It does not overwrite the original
51-scenario N=1000 baseline, tune scientific parameters, run T3, or execute E1–E5.

## Why the original Layer A used 51 scenarios

`configs/qfr_mechanism_layer_a_v1.json` explicitly points to
`configs/r6c_formal_ready_data_v2.json`. At the original execution commit this was the
production-ready QFR source with a complete scenario schema, commodity mapping, and
frozen reference budget. Its source contains 15 single-hurricane, 35 combined-hurricane,
and one no-hurricane scenario. The old output manifest records `scenario_count=51`.

The separate R6 Rawls24 delivery was intentionally data-only. Its manifest explicitly
excluded probability/weights, Formal commodity mapping, `F_bar`, and `B_ref`; therefore
it was not silently substituted into the original simulation. The old N=1000 output is
retained unchanged as a diagnostic baseline.

## Numerical-feasibility repair

T1 showed that solver-tolerance-scale residues could be accepted by
`validate_first_stage` and then make an exact recourse LP appear infeasible: a tiny
negative F fulfillment bound, or a first-stage cost exceeding B by only floating-point
residue. The exact-recourse builder now maps only already-accepted negative physical
residue to zero and uses B as the effective pre-disaster cost only when the accepted
raw cost is infinitesimally above B. Positive quantities and economically material
violations are unchanged. Decision identity, global tolerance, solver policy, model
objective, A1 search phases, stopping, and certification are unchanged.

## Rawls24 scientific/data chain

The scenario layer is the immutable `data/r6_rawls24` delivery: exactly `h01`–`h24`,
all real single-hurricane events. The unified Rawls demand is mapped mechanically with
the existing Formal mapping: Water=`water_unified`, Vaccine=`medical_unified ×
10.0603621730382`, and Crackers=`food_unified × 14`. `F_bar_i=max_h d_ih`.

Reference weights use the user-authorized Rawls-style nonnegative maximum-entropy
calibration with a uniform 1/24 prior, Florida mass 0.40, major-hurricane mass
0.4444444444, and minor mass 0.5555555556. The unique event-level group weights are
stored as high-precision decimal strings in
`configs/qfr_mechanism_layer_a_rawls24_v1.json`. They are used only for Dref and B_ref;
the robust min-max scenario mechanism remains unweighted.

For the neutral Layer A controls, h=0 and a=1. Thus
`Dref_i=sum_h p_h d_ih` and `B_ref=sum_i cQ_i Dref_i`. All other commodity economics
come unchanged from the hashed R6-C production template. No equal-probability rule or
new economic parameter is introduced.

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts\qfr_mechanism_layer_a_t2_regression.py
.\.venv\Scripts\python.exe scripts\qfr_mechanism_layer_a_rawls24.py prepare
.\.venv\Scripts\python.exe scripts\qfr_mechanism_layer_a_rawls24.py run
```
