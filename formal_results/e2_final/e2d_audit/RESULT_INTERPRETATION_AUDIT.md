# E2-D result-interpretation audit

The original raw results are unchanged. Cross-beta raw T-COST is not a common-welfare scale because beta is inside its shortage coefficient.

Diminishing-response verdict: **PARTIALLY_SUPPORTED**. Beta 2→4 improves the common-reference outcome for a minority of rows; beta 4→6 is an aggregate common-reference plateau, while some commodity composition changes remain.

Priority audit:

- E2D_LAMBDA_WATER: target benefit=True; non-target crowding-out=True; portfolio reference-cost increase=False.
- E2D_LAMBDA_VACCINE: target benefit=True; non-target crowding-out=True; portfolio reference-cost increase=True.
- E2D_LAMBDA_CRACKERS: target benefit=True; non-target crowding-out=True; portfolio reference-cost increase=True.

Claim-by-claim review:

- C1 — **SAFE_AS_WRITTEN**: Cross-beta raw T-COST rises mechanically because beta changes the objective coefficient. Production formula and common-reference evaluation confirm the scale change.
- C2 — **NEEDS_QUALIFICATION**: Raw aggregate physical shortage does not fall monotonically. Numerically true, but the sum combines gallons, doses, and 22-g service units and is descriptive only.
- C3 — **SAFE_AS_WRITTEN**: Beta 2 to 4 improves coefficient-normalized shortage value and beta 4 to 6 is unchanged. The common-reference shortage calculation reproduces this result.
- C4 — **NEEDS_QUALIFICATION**: Beta 4 to 6 exhibits a strong plateau. Reference-valued outcome and aggregate expenditures plateau, but commodity F/R and shortage composition still reallocate.
- C5 — **SAFE_AS_WRITTEN**: Each priority treatment reduces target shortage and transfers shortage to non-target commodities. Within-commodity physical and reference-valued paired comparisons agree.
- C6 — **SAFE_AS_WRITTEN**: Commodity responses differ by archetype. Paired Q/F/R and expenditure decompositions show distinct Water, Vaccine, and Crackers responses.
- C7 — **SAFE_AS_WRITTEN**: Same-item Q/F coexistence remains zero and h09 remains worst. Directly supported by frozen row-level evidence.
- C8 — **SAFE_AS_WRITTEN**: Commodity prioritization reallocates scarcity rather than eliminating it. All treatments show target benefit and non-target crowding-out under the common reference scale.

Scientific-freeze recommendation: **YES**, subject to independent review of this audit.
