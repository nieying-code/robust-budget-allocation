# R7-E1 Formal Main Experiment 执行报告

状态：**PASS — 等待独立复审**

## Identity 与执行边界

- execution commit：`736d0df3666667e875026e3eb45053d8ef222949`
- execution tree：`fccbbc0a8a22948ac7009db638ddea5f995d194f`
- Formal-ready data SHA-256：`3eaf0357d9d586198a8887c59b8e67ebeeb2ab8d7224923db854dca717f236f5`
- R6-B config identity：`ccf90d26d8947e2b0607d38c9812f69c485b5f1532fc5b9e9e8cd0b2abb7e0a2`
- E1 matrix identity：`cbedbec9643400af69b0d4369cfd0f1e0a0ccf4e9b61d26c5fc48717948f6b49`
- E1 cases：9；Formal scientific runs：9；certificate PASS：9
- E2–E5 runs：0；timing repetitions：0；`A1_no_memory` runs：0
- INVALID/INCOMPLETE runs：0

## Objective 与机制概览

| Case | Objective | Formal UB | Gap | F active | Paid R active | Worst scenario |
| --- | ---: | ---: | ---: | --- | --- | --- |
| B0.90_M0 | 206420135.1 | 206420135.1 | 0 | False | False | omega_21 |
| B0.90_M1 | 206420135.1 | 206420135.1 | 0 | False | False | omega_21 |
| B0.90_M2 | 204105876.6 | 204105876.6 | 0 | True | True | omega_21 |
| B1.00_M0 | 201828748.5 | 201828748.5 | 0 | False | False | omega_21 |
| B1.00_M1 | 201828748.5 | 201828748.5 | 0 | False | False | omega_21 |
| B1.00_M2 | 199257350.2 | 199257350.2 | 2.98023e-08 | True | True | omega_21 |
| B1.10_M0 | 197237362 | 197237362 | 0 | False | False | omega_21 |
| B1.10_M1 | 197237362 | 197237362 | 0 | False | False | omega_21 |
| B1.10_M2 | 194408823.8 | 194408823.8 | 0 | True | True | omega_21 |

同 budget 的 `M1-M0` 与 `M2-M1`、同 model 的 budget path、逐 commodity allocation、shortage、worst-scenario identity 与完整 mechanism activation 均保存在 `summary.json`。每个 case 的完整 `EF/A0/A1/certificate` 与 scenario accounting 保存在 `raw/`，summary 不替代 raw evidence。

## 认证与重放

9 个 cases 均通过 `verify_ef_a0_a1`、`validate_three_certificate` 与 Full Exact Certification。`HASHES.sha256` 覆盖 raw results、summary、manifest、run state 与本报告；deterministic non-solver summary regeneration 由 `replay` 验证。
