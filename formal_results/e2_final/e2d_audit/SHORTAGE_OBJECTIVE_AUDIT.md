# E2-D shortage-objective audit

Status: **PASS**. This audit is reconstructed from the production model and frozen
Final E1/E2-D configuration, not from narrative documentation.

For a fixed first-stage policy, production M2 uses

```text
C_pre = C_Q + C_F + C_R
E_omega = sum_i cE_i x_i,omega
S_omega = sum_i beta lambda_i cQ_i u_i,omega
L_omega = E_omega + S_omega
T-COST = C_pre + max_omega L_omega
```

The epigraph variable theta satisfies `theta >= L_omega` for every scenario and
the minimized objective is `C_pre + theta`. Emergency expenditure and shortage
penalty are separate components. The cash constraint is
`C_pre + E_omega <= B`; shortage loss is not cash expenditure.

`beta` multiplies the entire commodity shortage valuation; `lambda_i` multiplies
only commodity i; and the commodity-specific value coefficient is the acquisition
cost `cQ_i`. At the Final E1 reference, beta=4 and lambda=(1,1,1), so the shortage
coefficients are Water 2.5908 USD/gallon, Vaccine 55.664 USD/dose, and Crackers
0.37488 USD/22-g service unit.

`gamma_D=1` is applied in the frozen data/design construction. The optimization
model consumes the already-materialized demand matrix and does not multiply the
objective by gamma_D again. Shortage `u_i,omega` has the service unit of commodity
i: gallon, dose, or 22-g service unit.

The common-reference post-processing keeps the certified first-stage decision,
stored certified worst scenario, emergency expenditure, and shortage quantities
fixed, and replaces only the shortage coefficients by the Final E1 reference.
It performs no optimization and no new worst-scenario search.
