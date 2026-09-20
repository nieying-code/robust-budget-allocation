# E1-Historical Formal Experiment Report

Status: **PASS — ready for independent review**

## Research position

E1-Historical is the first formal component of E1. It validates the basic Q-F-R economic mechanism on the classical historical benchmark formed by Rawls' original 15 single-hurricane scenarios. E1-Extended will later use an independently constructed, larger real historical single-hurricane uncertainty set through 2025 to test whether the same mechanism persists under broader empirical uncertainty. This run does not perform or claim E1-Extended, E2–E5, or sensitivity analysis.

## Identity and derivation audit

- execution commit: `e4fc74225df2aa7d230b82a898831c626c67b3fc`; tree: `46c3226b1b0e69bc4a72c7e3c54a9ac667d04072`
- dataset: `rawls_15_single_hurricane_historical`; data SHA-256: `d1b48e13757f0ca6ff4919e26b8ed3f225b3f2b7764e9026d16fc2f985ff487c`
- ordered scenarios: `omega_01, omega_02, omega_03, omega_04, omega_05, omega_06, omega_07, omega_08, omega_09, omega_10, omega_11, omega_12, omega_13, omega_14, omega_15`
- scenario-set SHA-256: `7105246cea6da75ccdf9389ae1324be9b06ce4aa37b3ddd03c89da4bf88f1a55`
- parameter SHA-256: `00a23c63dc849239e52e5715dde96787cc20bf8d221349dee2adbc2f89f71039`
- B_ref formula: `sum_i((cQ_i+h_i*tau)*Dref_i/a_i)`
- old 51 B_ref: `7975014.2749022`; Rawls-15 B_ref: `6721988.79033174`
- old 51 F_bar: `{"Crackers": 206878000.0, "Seasonal Influenza Vaccine": 1144366.1971831, "Water": 27000000.0}`
- Rawls-15 F_bar: `{"Crackers": 186200000.0, "Seasonal Influenza Vaccine": 955734.406438632, "Water": 18000000.0}`
- B_ref and F_bar changes are mechanical applications of the same frozen formulas to the conditioned 15-scenario dataset, not recalibration.
- The authoritative source has hurricane IDs and categories but no hurricane-name field; names are recorded as unavailable rather than inferred.

## Nine-case results

| Case | T-COST | Q exp. | F exp. | R exp. | F | paid R | worst | cat |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: |
| B0.90_M0 | 115301534.5 | 6049789.911 | 0 | 0 | False | False | omega_13 | 5 |
| B0.90_M1 | 115301534.5 | 6049789.911 | 0 | 0 | False | False | omega_13 | 5 |
| B0.90_M2 | 114614729.5 | 0 | 1070759.276 | 1338449.095 | True | True | omega_13 | 5 |
| B1.00_M0 | 114156856.7 | 6721988.79 | 0 | 0 | False | False | omega_13 | 5 |
| B1.00_M1 | 114156856.7 | 6721988.79 | 0 | 0 | False | False | omega_13 | 5 |
| B1.00_M2 | 113383356.3 | 0 | 1189732.529 | 1487165.662 | True | True | omega_13 | 5 |
| B1.10_M0 | 113012178.9 | 7394187.669 | 0 | 0 | False | False | omega_13 | 5 |
| B1.10_M1 | 113012178.9 | 7394187.669 | 0 | 0 | False | False | omega_13 | 5 |
| B1.10_M2 | 112151983.2 | 0 | 1308705.782 | 1635882.228 | True | True | omega_13 | 5 |

Complete Q_i/F_i/R_i, worst-scenario demand/x/u, expenditures, utilization, near-worst rankings, all 15 scenario diagnostics, EF/A0/A1 evidence, and certificate identities are in `summary.json` and `raw/`.

## Validation and old-51 comparison

All nine cases passed EF/A0/A1 objective/feasibility consistency, memory-guided A1 convergence, and Full Exact Certification over exactly 15 scenarios. Deterministic replay and the output hash inventory passed.

The repository old-51 results are explicitly pre-revision historical diagnostic evidence. They used old eta0/delta/lambda values, whereas E1-Historical inherits the current frozen R6-C v2 values. Therefore numerical differences cannot be causally attributed to scenario-set deletion alone; no extra 51-scenario rerun was authorized.
The repository old 51-scenario results are preserved and were not modified. The machine-readable case-by-case comparison is `old_51_comparison.json`.
