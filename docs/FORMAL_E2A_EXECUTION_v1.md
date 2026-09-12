# Formal E2-A execution protocol

E2-A is the frozen OFAT commodity-heterogeneity mechanism test. It reuses the
1,000 canonical Final E1 parameter rows and baseline scientific results without
rerunning the baseline. Four new cells are solved with production M2 and
`A1_FINAL_NO_MEMORY_V1`:

- `E2A_VACCINE_H0`: Vaccine six-month cold-chain burden = 0.00 USD/dose;
- `E2A_VACCINE_H1`: Vaccine six-month cold-chain burden = 1.00 USD/dose;
- `E2A_CRACKERS_A100`: Crackers retention = 1.00;
- `E2A_CRACKERS_A080`: Crackers retention = 0.80.

The Vaccine cells retain Crackers retention 0.90. The Crackers cells retain the
Vaccine six-month cold-chain burden 0.50 USD/dose. Rawls24, demand, all sampled
Q/F/R parameters, beta 4, lambda `(1,1,1)`, gamma_D 1, and the absolute budget
19,137,905.85543848 are fixed. B_ref is not recomputed.

The run is paired by `LA-xxxx`; no draw may be dropped, replaced, or resampled.
Every failed solve is retained. Summaries are rebuilt from row-level outputs.
E2-B, E2-C, and E2-D are outside this execution and remain at zero runs.

## Final A1 numerical recertification

The initial execution certified 3,795 rows and retained 205 oracle failures. A
subsequent diagnostic identified 284 solver-infeasible scenario evaluations for
which conservative original-semantic recourse witnesses were feasible. After the
generic Final A1 witness-gated scaled-retry hotfix, the 205 original identities
were formally re-optimized through Candidate Search and Full Exact Certification.
All 205 certified. The complete 3,795 previously-certified population was also
replayed: Q/F/R, first-stage identities, policy labels, T-COST, worst scenarios,
certificates, and all serialized scientific quantities were invariant for
3,795/3,795 rows.

The final E2-A population is therefore 4,000/4,000 certified. The original
failure population and the complete replay evidence remain under
`formal_results/e2_final/e2a/recertification/`. This correction changed neither
the scientific design nor its samples and is not parameter tuning.

Final recertification commands:

```text
python scripts/recertify_formal_e2a.py recertify-failures
python scripts/recertify_formal_e2a.py regress-certified
python scripts/recertify_formal_e2a.py finalize
python scripts/recertify_formal_e2a.py verify
```

Reproduction commands:

```text
python scripts/run_formal_e2a.py preflight
python scripts/run_formal_e2a.py run-case --case E2A_VACCINE_H0
python scripts/run_formal_e2a.py run-case --case E2A_VACCINE_H1
python scripts/run_formal_e2a.py run-case --case E2A_CRACKERS_A100
python scripts/run_formal_e2a.py run-case --case E2A_CRACKERS_A080
python scripts/run_formal_e2a.py finalize
```
