# E3-B frozen design recovery

`E3B_DESIGN_RECOVERY_STATUS = PASS`

- Panel: frozen S200 (`2b7d7a92c9a0301203a6b73a349a32903b83434038dc88a52fe1cc734ffad32d`), 200 background rows per cell.
- S100 used: NO. S100 is frozen for E4-B only.
- F-risk donors: Low LA-0975, Medium LA-0169, High LA-0794; only `rho_F1..rho_F5` are donated.
- Reliability donors: Unfavorable LA-0374, Reference LA-0427, Favorable LA-0755; only `eta_1`, `eta_2`, `c_R1_ratio`, `c_R2_ratio` are donated.
- Background row supplies `rho_Q1..rho_Q5`, `phi`, and `psi`.
- Each of the 9 crossed treatments is applied to every background row: 9 x 200 = 1,800 optimizations.
- Fixed environment: B=19,137,905.85543848; beta=4; lambda=(1,1,1); gamma_D=1; Vaccine h*tau=.50; Crackers a=.90; Rawls24 h01-h24.
- Reliability ratios are multiplied by each commodity's frozen cQ. No item-specific donor or new parameter is introduced.
