# R7-E1 Formal Main Experiment Protocol v1

状态：**在第一个 R7-E1 Formal scientific run 前冻结**

## 范围

R7-E1 只执行 R6-B 的 9 个 `E1_cases`：`M0/M1/M2` 与
`B/B_ref = 0.90/1.00/1.10` 的笛卡尔积。不生成或执行 E2、E3、E4、E5
case，不做 timing repetition，也不调用 `A1_no_memory`。

## 权威输入

runner 只能通过 `configs/r6_formal_experiment_matrix_v1.json` 与 R6 delivery
manifest 解析 Formal-ready dataset。任何 Formal data、R6-B config、expanded
matrix 或 human specification identity 不一致都会失败关闭。随后从已提交的
`qfr_data` payload 构造 case，仅将 `budget` 设为 R6-B 登记的 ratio 乘以冻结
`B_ref`。

## 求解与认证链

每个已登记 E1 case 计为 1 个 Formal scientific case。每个 case 只执行 1 次
既有审查链：`EF`、`A0`、`A1_full`，其中
`memory_phase_enabled=True`；`verify_ef_a0_a1` 与
`validate_three_certificate` 必须 PASS。`A1` convergence 与 formal UB 仍只能
由覆盖全部 51 scenarios 的 Full Exact Certification 给出。这三个 method 是
单个 E1 case 的 certificate components，不是 E5 timing competitors。

冻结 solver policy 保持 CPython 3.12.10、Pyomo 6.10.1、
gurobipy/Gurobi 13.0.2、`gurobi_direct`、`Threads=1`、no fallback 与 R3
numerical policy。

## 输出与失败规则

输出根目录为 `experiments/r7_e1`。如果该路径已经存在，runner 拒绝启动。每个
case 原子写入唯一文件名，文件名包含其 R6-B experiment identity。raw
`EF/A0/A1/certificate` evidence 完整保留；summary 与 inventory 只能从 raw
results 派生。

如果 Formal execution 启动后出现任何异常，runner 立即停止剩余 cases，并将
`RUN_STATE.json` 原子写为 `INVALID`，保留已完成 case identities 与错误；不得
覆盖或续跑既有 Formal output root。

## 描述性服务指标

scenario total shortage 是各 commodity shortage quantity 之和；demand
satisfaction 为 `1 - total_shortage / total_demand`，zero-demand scenario 定义为
完全满足。probability-weighted shortage 使用冻结的 R6 scenario probabilities。
`active_worst_scenario` 是 complete exact oracle 的 robust-cost worst scenario；
`maximum_shortage_scenario` 单独报告，不得替换 robust-cost worst case。
