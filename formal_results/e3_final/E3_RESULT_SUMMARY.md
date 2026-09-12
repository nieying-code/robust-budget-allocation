# Formal E3 targeted-interaction result summary

E3-A and E3-B each completed 1,800/1,800 Full Exact Certified paired optimizations (3,600/3,600 overall; zero failures).

## E3-A

Vaccine preservation burden affects sourcing conditionally. At favorable F economics (mF=.8), Vaccine Q is already zero throughout S200, so higher preservation cost cannot induce an additional Q-to-F regime switch. At mF=1.0 and 1.2, preservation burden reduces Vaccine Q, but Vaccine F and paid-R responses are heterogeneous/nonmonotonic. The interaction is economically visible mainly in allocation intensity and a small number of regime changes. Detailed paired contrasts are in `e3a/interaction_contrasts.csv`.

## E3-B

F disruption risk raises the value of reliability conditionally: no Low- or Medium-risk cell selects paid R, whereas all paid-R observations occur at High risk. Reliability economics changes the paid level (Unfavorable donors select R1; Reference/Favorable donors select R2), but aggregate paid-R adoption across the three donor levels is nonmonotonic. F-risk x reliability-efficiency complementarity is therefore **PARTIALLY_SUPPORTED**, not a universal monotone relation.

## Shared findings

- h09/Katrina is the worst scenario in all 3,600 results.
- Interactions primarily alter allocation intensity; policy-regime changes are sparse and concentrated in selected cells.
- Some local effects are nonmonotonic and are retained as scientific evidence.
- Physical shortage is interpreted within commodity units; raw cross-unit totals are descriptive only.
- No resampling, representative-row reselection, result-driven tuning, model/tolerance change, or E4 execution occurred.
