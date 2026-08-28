# N6 prelaunch engineering diagnostic

The first launch at execution commit 29a74e5f4499c36fbc28940f73bbd8283e015059
stopped in source_gate BEFORE the batch directory, any run_id, worker, preflight
or scientific solve was created. The error was:

    execution found untracked scientific inputs:
    src/robust_budget_allocation.egg-info/PKG-INFO
    src/robust_budget_allocation.egg-info/SOURCES.txt
    src/robust_budget_allocation.egg-info/dependency_links.txt
    src/robust_budget_allocation.egg-info/requires.txt
    src/robust_budget_allocation.egg-info/top_level.txt

These are ignored editable-install packaging metadata, not scientific inputs.
The N6 caller incorrectly passed src as a scientific root. The local correction
uses src/robust_budget_allocation, matching frozen N4/N5 runner practice; all
actual package code, tests, scripts and configs remain protected. Required
execution paths remain Git tracked and content hashed. The frozen N1 gate is
unchanged. Added a regression test for the caller scope.

This is a prelaunch engineering correction, not a retry/replacement of a pilot
run, not a scientific parameter adjustment, and not a model/algorithm correctness
failure. There were zero pilot results to inspect. The protocol/config hashes are
unchanged. No failed pilot run was overwritten or deleted.

