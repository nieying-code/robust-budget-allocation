# N6 scientific informativeness diagnosis — complete fresh n6pilot02

PILOT ONLY — NOT FORMAL SCIENTIFIC PARAMETERS.
Current assessment: N6_READY_FOR_PR_REVIEW under the preregistered severe-risk
criteria, WITH persistent Option and Memory coverage/claim warnings. No N7 entry
or merge is authorized. No scientific definition or candidate value was changed.

N6 PR #7 was merged prematurely before full pilot completion. This merge is a
governance event only and does not constitute N6 scientific approval, readiness,
or authorization to enter N7.

Merge ce12e391f503ca877605f860256a1f86e11d59d8 at 2026-08-28T02:22:07Z occurred
while N6 was BLOCKED and the full pilot incomplete. The current independent
80-run batch uses ec6bbfc55e333483efa41f866c0e8f26d13cd18f /
1856c203917fa3cc234f5aee83e2a4403abe472d only, not old M0/M1 or diagnostic results.
All 80 certificates and 16 EF/A0/A1 groups replay; max A0/A1 objective difference
is zero. Original blocked history is retained below and in separate archives.

## MODEL — observed responses and their limits

M2=M1 in all 16 configurations; y_F=0 and E=g=0 in every scenario. Paid Reliability
is selected in 12/16 M2 configurations; M1 improves on M0 in the same 12.
It is not an across-the-board M0=M1=M2/constant-Quantity degeneration.

| Matched example | Quantity | C_R | Paid suppliers | Unused cash |
| --- | ---: | ---: | ---: | ---: |
| Low risk, seed61001, B45 | 40.39894 | 0 | 0 | 0 |
| Low risk, seed61001, B90 | 72.74074 | 12.80000 | 1 | 0 |
| Low risk, seed61001, B150 | 101.96740 | 19.12975 | 2 | 17.69586 |
| High risk, seed61001, B45 | 36.44068 | 8.55932 | 1 | 0 |
| High risk, seed61001, B90 | 70.72993 | 17.66058 | 2 | 0 |
| High risk, seed61001, B90, premium x2 | 63.82609 | 25.60000 | 1 | 0 |

All rows have y_F=0. At equal tight budget, higher risk reallocates cash from
Quantity to Reliability. At B90, doubled premium reduces the number of paid
suppliers from two to one and Quantity from 70.72993 to 63.82609, despite higher
total premium spending. This is a cost/quantity/protection response, not a
claim that higher premium always increases Reliability spending. All four B150
primary cases leave positive unused cash; unused resources occur in lower-demand
scenarios. Neither unused cash nor unused resources are counted as Flexibility.
The full 16 configuration table and exact q/objectives are in N6_PILOT02_SUMMARY.json.

Option nonactivation is universal WITHIN this registered finite sample, including
the high-risk cases and fee-doubling contrast. No observed Q/R/F cross-stage
exercise trade-off or complementarity can be claimed. The model's same-B
constraint is verified, but its active F exercise effect is not demonstrated.
Fee-doubling an already unselected option is not informative about its entry
threshold. This is an important scope limitation, not something to hide behind
the nonblocking aggregate criterion.

Cause classification, without additional solving or tuning:

- A (economic calibration): candidate price 2.2–4 exceeds advance costs 1–1.35
  but stays below penalty8; fee6/12 and cap45 have coherent illustrative units.
  This rules out a simple sign/unit-domain error, not an empirically established
  calibration. Paying fee and exercise cash from the same B can compete strongly
  with reliable advance procurement. This is a plausible explanation, not an
  identified causal dominance proof.
- B (coverage): only two seeds, one base fee/cap and one higher-fee contrast;
  neither an independently calibrated lower-fee region nor a distinct emergency
  price regime was covered. Broad mechanism entry claims are unsupported.
- C (structure): no proof of universally useless Option or a mathematical flaw.
  Q and R respond; full model-wide severe-degeneration predicate is false.
  Nonactivation here cannot exclude structural limitations in other settings.
- E (small sample): 16 dependent/matched configurations are not 16 independent
  empirical trials; uncertainty cannot be resolved with significance claims.

No new range, fixture or solve was added. External review should decide whether
future N7 scope must explicitly limit F claims or needs separately authorized,
theory/calibration-grounded diagnosis. These candidate values cannot automatically
become formal parameters because some mechanisms produced useful-looking results.

## ALGORITHM — Candidate works; Memory benefit remains unobserved

Across 16 paired runs: A0 42 exact calls/576 scenario evaluations; A1 16 complete
exact calls/258 evaluations. Both have 42 iterations total, range2–4, active
sets2–4, and26 added scenarios. A1 Phase I hits0; Phase II hits26; Phase III calls16.
Every A1 run has one terminal full exact certificate; 26 nonterminal iterations
skip full search after an exact candidate violation. No Phase I/II UB fabrication.

Trace diagnosis, not just hit counts: all42 A1 master states have y_F=0. All42
Phase I rankings/evaluation lists are empty. Before termination, Memory contains
candidate-hit scenarios already added to the active set; these are correctly
ineligible. The first full-oracle memory population occurs at termination, with
no later iteration that could exploit it. Thus this sample cannot measure Memory
rediscovery benefit. It is inactivity by the frozen eligibility/state sequence,
not evidence of a broken Memory implementation.

At y_F=0, the fixed candidate shortage-exposure score equals the mathematical
recourse loss (no emergency exercise). This explains why Candidate screening is
especially informative here. It also limits extrapolation to option-active
instances, where the score deliberately ignores exercise and price. No claim
that all three search phases provide independent performance gains is supported.

A1 median algorithm time0.2751s versus A0 0.5992s, with observed maxima0.5055s
and1.6038s. These descriptive measured-size observations are not a formal speedup
estimate or proof of algorithmic novelty. Paired oracle/evaluation workload is
lower, so the preregistered overhead-only severe A1 predicate is not triggered.
Memory inactivity remains a narrow B/D/E coverage/mechanism/claim risk; larger
or different instances are not automatically authorized to make Memory look good.

## Decision and capacity

Execution, exactness and replay PASS. Pre-registered model-wide and algorithm-wide
severe predicates are false, so current submission is N6_READY_FOR_PR_REVIEW, NOT
an assertion that every mechanism is informative. Option nonactivation and Memory
inactivity must be considered explicitly by external reviewers before N7.
The current evidence supports Q/R response, candidate-search workload reduction,
trustworthy execution and measured-size capacity only. It does NOT establish F
value, Memory benefit, general superiority, empirical realism or formal effects.

At measured12/24 scenarios, illustrative1000 A0/A1 pairs require median3.25h
supervisor time, observed-slow3.62h, or7.25h with the registered2x contingency,
plus batch audit/coordination/gates. Raw paired payload estimates are229.93–383.96MB,
or767.93MB with2x contingency, excluding manifests. See report for timing bounds
and all arithmetic. This is practical local capacity, not an N7 matrix or OOS
projection. No N7 parameters, seeds or scale decisions have been frozen.

Keep PR #8 Draft; stop for external review. No merge, N7 or formal experiments.

---

# Historical incomplete-coverage diagnosis (retained; not the current state)

PILOT ONLY — NOT FORMAL SCIENTIFIC PARAMETERS

Subsequent authorized harness-only update: the single new-source EF diagnostic
n6diagnostic01-ef-retry PASSED. See N6_HARNESS_REPAIR_REPORT.md and the separate
diagnostic manifest. It cannot be pooled with old M0/M1 and adds no paired or
cross-configuration scientific evidence. All MODEL/ALGORITHM conclusions below
remain NOT ASSESSABLE. Further pilot work and N7 remain unauthorized.

Final stage state: **N6_BLOCKED**, due to supervised execution I/O, NOT a finding
that the frozen scientific design is wrong. Diagnosis of scientific risk remains
**NOT ASSESSABLE**. Do not interpret machine summary boolean flags on an empty
paired dataset as evidence of absence of risk.

## MODEL

Observed: only low-s61001-b45-n12, B45, 12 scenarios and three suppliers.
M0 and M1 succeeded with equal T-COST 495.7182976095696, base Reliability and
total q=40.398938656534916. The EF worker's saved optimum matches, with y_F=0,
but its supervisor failed and it is not an accepted pilot run.

This limited point is compatible with legitimate mechanism nonactivation.
It cannot establish that M2 always equals M1, Reliability is always at base,
Option is never useful, or Quantity/Reliability/Flexibility lack response.
No matched budget, risk, premium, Option-fee or scenario-size contrast completed.
No across-stage substitution/complementarity or response pattern can be diagnosed.

The normalized candidate values have preregistered relative-cost rationale, not
empirical calibration. There is no result-driven change to fee/cap/premium.
Risk classes A (economic calibration), B (coverage), C (model structure) and E
(small sample) cannot be distinguished scientifically. The immediate limitation
is B/E: nearly all registered coverage was never executed. No claim of a
structural flaw, nor a claim of successful innovation, is supported.

## ALGORITHM

A0 runs=0, A1 runs=0, completed pairs=0. Phase I/II hits, Phase III/full-oracle
calls, scenario evaluations, active-set sizes and runtime comparisons are
unobserved, NOT zero-effect estimates. No Memory/candidate effectiveness,
overhead-only degeneration, speed advantage or workload reduction conclusion
is possible. D (A1 mechanism effectiveness) is unassessed; B/E dominate.

N4/N5 correctness evidence remains intact, but is not substituted for N6
workload observations. No scoring/candidate/memory/state-machine definition was
changed. No additional pilot is authorized merely to obtain attractive results.

## Execution cause and decision

The EF supervisor recorded PermissionError and marked the run incomplete,
although its saved raw mathematical certificate passes read-only replay.
A concurrent Windows heartbeat read/atomic-replace conflict is plausible;
missing traceback/filename means the precise cause is not yet proven.
See N6_PILOT_REPORT.md for immutable anchors and failure details.

The full failed run is retained. No model/algorithm fix or configuration addition
was attempted. The later, explicitly authorized harness repair and one EF retry
are separately documented, preserving parent/run lineage and the old failure.
Keep PR #7 Draft; pause N7. External review must decide whether to authorize any
new same-source full batch. Only trustworthy and sufficient coverage can support
scientific informativeness judgments.
