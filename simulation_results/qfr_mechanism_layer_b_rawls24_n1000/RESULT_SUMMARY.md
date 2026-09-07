# Rawls24 Layer B N=1000 result summary

## Run outcome

- Requested / attempted / successful / exact certified: `1000 / 1000 / 1000 / 1000`.
- Failures: `0`.
- Sample table SHA-256: `ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0`.
- Layer B `B_ref`: `19,137,905.85543848`; paired homogeneous Layer A `B_ref`: `18,146,405.511449322`.
- Policy counts: P1 `208`, P2 `26`, P3a `4`, P3b `3`, P4 `759`, P5 `0`.
- Aggregate item-level reliability counts: NONE `1840`, R0 `1023`, R1 `86`, R2 `51`.
- Worst scenario: h09 / Katrina in `1000/1000` draws.

## Commodity activation

| Commodity | Q active | F active | NONE | R0 | R1 | R2 |
|---|---:|---:|---:|---:|---:|---:|
| Water | 241 | 356 | 644 | 343 | 5 | 8 |
| Seasonal Influenza Vaccine | 208 | 225 | 775 | 158 | 49 | 18 |
| Crackers | 0 | 579 | 421 | 522 | 32 | 25 |

Layer B contains 33 aggregate mixed Q+F policies. All 33 transition from homogeneous
Layer A P1: 26 to P2, four to P3a, and three to P3b. The mixing is cross-commodity,
not within one commodity. In 24 draws Q is Water and F is Crackers; in nine draws Q
is Water and F is Vaccine. No draw has Q and F simultaneously positive for the same
commodity. The 759 Layer A F-dominant draws remain P4.

## Paired effect relative to homogeneous Layer A

- Mean delta T-COST (Layer B minus Layer A): `-1,923,400.9441`; median:
  `-1,760,981.5219`; range: `[-6,603,652.3024, -505,416.1777]`.
- Mean delta Q: Water `+1,967,740.5254`, Vaccine `-64,922.2877`, Crackers
  `-5,036,055.1137` service units.
- Mean delta F: Water `+399,345.4551`, Vaccine `+48,726.0359`, Crackers
  `+4,335,076.4955` service units.
- Budget usage remains at one up to numerical precision in every draw.

These are paired descriptive changes under the required `B=1.0*B_ref`; restoring
the frozen h/a values mechanically changes B_ref. They are not a causal parameter
calibration claim.

## h09 dominance audit

h09 is not componentwise demand-dominant. h12/Dennis, h17/Rita, h19/Irma,
h20/Charley, and h23/Jeanne each exceed h09 in Water demand. No other scenario
exceeds h09 in mapped Vaccine or Crackers demand. h09 is Category 5, so no lower
category has worse Q or F availability for any admissible draw.

Despite the lack of full demand dominance, h09 has the largest exact recourse loss in
all 1000 Layer B solutions. h19 is the nearest non-h09 scenario in all 1000 draws.
The h09 loss advantage is strictly positive in all draws: absolute range
`928,405,468.76` to `1,032,229,685.43`, relative range `0.8096` to `0.8510` of h09
loss. Thus the lock is a strong sampled robust-loss dominance driven by h09's extreme
Vaccine/Crackers exposure plus Cat5 availability, not literal componentwise demand
dominance.

This summary is exploratory evidence only. No model, algorithm, tolerance, Q/F/R
parameter, Rawls24 data, or sampling rule was changed based on these results.
