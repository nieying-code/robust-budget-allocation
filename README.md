# Robust Budget Allocation

This is a new, independent research repository for two-stage robust allocation of a finite budget among **quantity**, **reliability**, and **flexibility**. It is not a continuation, fork, or revision of the frozen legacy project.

## Research scope

The project will compare three nested model families:

- **M0 — Quantity baseline:** ex-ante resource quantities with scenario-dependent recourse.
- **M1 — Quantity + Reliability:** adds paid reliability choices that change scenario-contingent fulfillment.
- **M2 — Quantity + Reliability + Flexibility:** adds a separately budgeted resource whose use is decided after uncertainty is revealed.

The exact algorithmic baseline is **A0, Standard Column-and-Constraint Generation (C&CG)**. The proposed **A1, Memory-Guided Multistage C&CG**, may use memory and candidate search to find violated scenarios early, but only a complete exact oracle may certify an upper bound or convergence.

No empirical performance or superiority claim has been established in this repository.

## Locked solver environment

- Python `3.12.10`
- Pyomo `6.10.1`
- gurobipy `13.0.2`
- Gurobi Optimizer `13.0.2`
- Pyomo interface `gurobi_direct`
- Gurobi `Threads=1`

Create the environment with the exact Python interpreter, install the locked requirements, and run the preflight before any scenario generation or solve:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\environment_preflight.py
```

The preflight fails fast. It never installs packages, changes versions, or falls back to another solver.

## Tests

Solver-free tests are the default CI gate:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not gurobi"
```

Tests marked `gurobi` require the locked local environment and a valid Gurobi license:

```powershell
.\.venv\Scripts\python.exe -m pytest -m gurobi
```

## Project status

The current milestone is N0: research design and repository/environment setup. Formal M1/M2/A1 implementation and formal experiments are prohibited until the open scientific decisions are confirmed and the model is frozen.

The design package is maintained outside this Git repository at `01_new_project_design` under the project root. Legacy materials remain read-only in `00_legacy_freeze`.
