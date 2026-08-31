# R6-A Formal Data Recovery and Preparation Report

Status: **DATA STAGE READY FOR INDEPENDENT REVIEW; NO FORMAL SCIENTIFIC SOLVES**

## 1. Scope and active baseline

This delivery implements only the deterministic data chain

`source evidence -> source data -> transformations -> Formal-ready data`.

The sole active Formal commodity set is **Water + Seasonal Influenza Vaccine + Crackers**. Insulin, Medical Oxygen, IV Saline, common-Water-exposure mapping, `D_C=D_W`, and the old common-Water-cost shortage formula are superseded and are not consumed by the active pipeline. Historical documents are not rewritten.

No M0/M1/M2, EF, A0, A1, sensitivity, OOS, timing, or R7 run was performed. `Formal scientific runs = 0`; R6-B has not started.

## 2. Sources actually recovered

Rawls and Turnquist (2010) is the primary Gulf Coast source. Tables 2-4 provide commodity units/costs, 15 source hurricanes, and 51 scenario identities/probabilities. Yang et al. (2021), Tables 12-13, independently reproduce the same event/scenario values; the reconstruction found no substantive discrepancy.

The source structure is exactly 15 single-hurricane scenarios, 35 two-hurricane scenarios, and one no-hurricane scenario. The probabilities sum to 1.0. Combined demands are sums of the source event demands; the registered combined category is the maximum constituent category. The no-hurricane row has zero demand, `rho_Q=1`, and `delta_F=0`.

The JPPR paper supplies literature-calibrated category case settings, not observed damage rates. Hu and Dong and its Mendeley workbook are auxiliary only: the workbook has one effective region `scenario!A1:AA41`, 40 non-empty scenario rows, 25 demand columns, and probability sum 1. It is not an 81-scenario Rawls source and contributes no active Formal calculation. The separate Yunnan/tent paper is methodological auxiliary material and is not Gulf Coast provenance.

Detailed source identities and SHA-256 values are in `docs/evidence/R6_SOURCE_INVENTORY_v1.json`; field-level classifications are in `docs/evidence/R6_FORMAL_DATA_PROVENANCE_v1.csv`.

## 3. Demand transformations

The three mappings deliberately have different meanings:

| Commodity | Source field | Transformation | Meaning |
| --- | --- | ---: | --- |
| Water | Rawls Water (1000 gallons) | `d_W = 1000 * Water_raw` | physical unit conversion |
| Seasonal Influenza Vaccine | Rawls abstract Medical | `d_V = (140 / 13.916) * Medical_raw` | economic-scale-preserving service normalization |
| Crackers | Rawls MRE (1000 meals) | `d_C = 14 * 1000 * MRE_raw` | approximate energy-service normalization |

The exact implemented Vaccine multiplier is `140/13.916 = 10.0603621730382`. It is not a medical conversion and does not say that one medical kit equals 10.06 doses. The identity `13.916*d_V = 140*Medical_raw` is tested.

The Crackers coefficient `14` uses the registered approximation `1250 kcal per MRE / 90 kcal per 22 g crackers service ≈ 14`. It is not a statement of physical package equivalence. No person-day or global response horizon was introduced.

The canonical source table is `docs/evidence/R6_SOURCE_SCENARIO_TABLE_v1.csv`; the long-form transformation table is `docs/evidence/R6_FORMAL_DEMAND_TRANSFORMATION_v1.csv`; the machine-readable result is `configs/r6_formal_ready_data_v1.json`.

## 4. Active parameter table

| Commodity | Formal SU | cQ | h per month | tau | h*tau | a | cF | pF | shortage s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Water | 1 gallon | 0.6477 | 0 | 6 | 0 | 1.00 | 0.12954 | 0.550545 | 3.8862 |
| Seasonal Influenza Vaccine | 1 dose | 13.916 | 1/12 (display 0.08333) | 6 | 0.50 | 1.00 | 2.7832 | 11.8286 | 139.16 |
| Crackers | 22 g serving | 0.09372 | 0 | 6 | 0 | 0.90 | 0.018744 | 0.079662 | 0.37488 |

Vaccine `h` is stored as the exact `0.50/6 = 1/12`; `0.08333` is display rounding. Vaccine refrigeration is a cold-chain carrying burden, not purchase cost, spoilage, hurricane loss, or retention. Crackers `a=0.90` is storage-adjusted effective service retention, not an observed 10% mass loss.

Shortage uses `s_i=4*lambda_i*cQ_i` with priorities Vaccine 2.5, Water 1.5, Crackers 1. Shortage enters the objective only, never the fixed cash budget.

F uses `(phi,psi)=(0.20,0.85)`, so reservation plus fully exercised base cost is `1.05*cQ`. Vaccine reconstructs `cF+pF=14.6118`, versus Q effective preparation cost `13.916+0.50=14.416`; the ratio is `1.013582130965594`. F therefore has no pure-price arbitrage advantage over Q. The registered but unexecuted split configurations are `(0.10,0.95)`, `(0.20,0.85)`, and `(0.30,0.75)`.

Reliability remains `eta=(0,0.50,0.80)` with premium ratios `(0,0.10,0.25)`. It protects only F. Category mappings remain:

| Category | rho_Q | delta_F |
| ---: | ---: | ---: |
| 1 | 0.80 | 0.10 |
| 2 | 0.60 | 0.30 |
| 3 | 0.40 | 0.60 |
| 4 | 0.20 | 1.00 |
| 5 | 0.00 | 1.00 |

## 5. Capacity and reference budget

The governing `Fbar_i=max_omega d_iomega` rule is applied to all 51 transformed scenarios without reference to optimization outcomes:

| Commodity | Fbar |
| --- | ---: |
| Water | 27,000,000 |
| Seasonal Influenza Vaccine | 1,144,366.1971831 |
| Crackers | 206,878,000 |

R6-A registers `Dref_i` as the probability-weighted mean over the complete source scenario distribution:

| Commodity | Dref | Q reference component |
| --- | ---: | ---: |
| Water | 4,325,654.88 | 2,801,726.665776 |
| Seasonal Influenza Vaccine | 146,257.388732394 | 2,108,446.5159662 |
| Crackers | 29,431,892.7 | 3,064,841.09316 |

Using `B_ref=sum_i((cQ_i+h_i*tau)*Dref_i/a_i)` gives **7,975,014.2749022 USD**. This is a deterministic data calibration only. The planned 0.90/1.00/1.10 ratios were not solved.

## 6. Mandatory 51-scenario scale audit

All absolute statistics include the zero-demand no-hurricane row. Scenario-share statistics exclude that single undefined `0/0` row.

### Effective pre-disaster Q exposure

| Commodity | min | median | mean | max | probability-weighted mean | share min | share median | share mean | share max | weighted aggregate share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Water | 0 | 2,428,875 | 4,181,309.9 | 17,487,900 | 2,801,726.665776 | 1.9905% | 42.0974% | 45.1439% | 90.1494% | 35.1313% |
| Vaccine | 0 | 710,937.947686 | 2,356,709.161636 | 16,497,183.098592 | 2,108,446.515966 | 3.1840% | 7.4866% | 16.1743% | 46.7498% | 26.4382% |
| Crackers | 0 | 2,667,896 | 4,108,925.735948 | 21,542,895.733333 | 3,064,841.09316 | 5.7604% | 36.8520% | 38.6819% | 74.8228% | 38.4305% |

Commodity-heavy rows by within-scenario Q-exposure share are Water `omega_07`, Vaccine `omega_03`, and Crackers `omega_15`.

### Shortage exposure

| Commodity | min | median | mean | max | probability-weighted mean | share min | share median | share mean | share max | weighted aggregate share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Water | 0 | 14,573,250 | 25,087,859.4 | 104,927,400 | 16,810,359.994656 | 1.95396% | 42.3388% | 47.8922% | 89.9819% | 34.8785% |
| Vaccine | 0 | 6,862,800 | 22,749,698.039216 | 159,250,000 | 20,353,178.216 | 5.7883% | 15.8955% | 26.2419% | 64.2996% | 42.2292% |
| Crackers | 0 | 9,604,425.6 | 14,792,132.649412 | 77,554,424.64 | 11,033,427.935376 | 3.4498% | 23.1790% | 25.8660% | 60.3504% | 22.8924% |

Commodity-heavy shortage rows are Water `omega_07`, Vaccine `omega_13`, and Crackers `omega_15`. No commodity crosses the registered unexplained scale guard (`>99%` or `<0.01%`) in either exposure family. The observed variation follows the heterogeneous source demand patterns rather than a common exposure multiplier; no rescaling was performed.

## 7. Reproducibility and limitations

`scripts/r6_prepare_formal_data.py` regenerates both scenario CSVs and the complete Formal-ready JSON. The JSON includes the production `QFRData` representation and builds successfully under schema v3 without invoking a solver. Tests cover 51 rows, 15/35/1 composition, probability, identity, worst-category aggregation, all three transformations, economic normalization, retention, shortage, F/R costs, zero-demand handling, deterministic regeneration, and absence of active superseded commodities.

The public CDC price anchor is the 2025-2026 adult Fluarix TIV contract row (NDC 58160-0912-52, USD 13.916/dose). The exact numerical Vaccine carrying cost and Crackers price/retention remain explicitly classified as research calibration rather than misrepresented as direct empirical observations. This is not an unresolved scientific block because these values were explicitly frozen by the final R6-A instruction.

No genuine scientific block remains. R6-B, the Formal experiment matrix, all scientific optimization runs, and R7 remain deferred pending independent data review.
