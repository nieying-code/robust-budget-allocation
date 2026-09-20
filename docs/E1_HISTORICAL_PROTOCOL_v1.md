# E1-Historical Formal Protocol v1

## Research position and boundary

E1-Historical is the first formal component of E1. Its purpose is to validate the
basic Q-F-R economic mechanism on the classical historical benchmark formed by
Rawls' original 15 single-hurricane scenarios. A later, separately constructed
E1-Extended dataset will test the same mechanism on a larger real historical
single-hurricane uncertainty set through 2025. This protocol does not perform or
claim E1-Extended, E2--E5, sensitivity analysis, or parameter calibration.

The dataset identity is `rawls_15_single_hurricane_historical`. Its ordered
scenario IDs are `omega_01` through `omega_15`, exactly the 15 rows classified as
`single` in the frozen R6-C v2 source. Combined scenarios `omega_16`--`omega_50`
and no-hurricane `omega_51` are excluded. The source provides hurricane IDs
`h01`--`h15` (in the source scenario order) and categories, but no hurricane-name
field; names must therefore remain unavailable rather than inferred.

## Mechanical dataset derivation

All model and economic parameters are inherited byte-for-byte from
`configs/r6c_formal_ready_data_v2.json`. The only design change is the scenario
set. Rawls' original probabilities on the selected 15 rows sum to 0.75 and are
conditioned on the selected subset by `p_H(omega)=p_51(omega)/0.75`.

The frozen rules are then applied mechanically:

- `Dref_i = sum_{omega in Omega_H} p_H(omega) d_iomega`;
- `B_ref = sum_i ((cQ_i+h_i*tau) Dref_i / a_i)`;
- `Fbar_i = max_{omega in Omega_H} d_iomega`.

No value is chosen from optimizer behavior. The derived data file records old and
new values, differences, source/data/scenario-set/parameter hashes, and ordering.

## Formal matrix and algorithm chain

Exactly nine cases are executed: M0/M1/M2 crossed with 0.90/1.00/1.10 B_ref.
Each case runs the existing frozen chain once: EF, A0, and memory-guided A1 with
Memory Inspection, Candidate Search, and Full Exact Certification. The existing
master/subproblem formulations, memory/candidate logic, ranking, convergence,
tolerances, solver policy, and certificate chain are imported unchanged.

The solver is `gurobi_direct`, one thread, no fallback. Activation patterns are
scientific results, not pass/fail gates. Correct identities, complete execution,
EF/A0/A1 consistency, full exact certification, and deterministic replay are hard
gates.

## Outputs and failure behavior

The exclusive output root is `experiments/e1_historical_rawls15`. Raw case files
retain complete EF/A0/A1/certificate evidence and all 15 scenario recourse rows.
The summary, comparison, report, manifest, run state, and SHA-256 inventory are
derived from those raw files. The runner fails closed if the first execution does
not start from the required clean committed branch or if the output root exists.
It never resumes or overwrites a formal output directory.
