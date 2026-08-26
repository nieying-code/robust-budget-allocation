# ALGORITHM SPEC v1

状态：N0 最终算法方向；A1 scoring 与 memory 生命周期按计划在进入 N5 前冻结。

## 1. 共同问题口径

对 M∈{M0,M1,M2}，Stage 1 成本为 c(x)=C_Q+C_R+K_Fy_F；固定 x 后：

    Q_ω(x)=min E_ω+Σ_i s_i u_iω

满足场景资源平衡、Option 合同上限和统一预算 `c(x)+E_ω≤B`。完整问题为 `min_x c(x)+max_ω Q_ω(x)`。A0、A1 与 Extensive Form 必须调用同一模型 builder、同一 Ω、同一 recourse 和同一 T-COST 口径。

## 2. 共同接口

- `solve_master(S)`：对有序 S⊆Ω 求受限 MP，返回 x、η、objective 和 solver status。
- `evaluate_scenario(x,ω)`：精确求 Q_ω(x)，返回 recourse、场景预算、平衡与状态证据。
- `exact_oracle(x,Ω)`：对完整有限 Ω 精确求 max_ω Q_ω(x)，按冻结 tie-break 返回最坏场景。
- `violation(x,ω,η)=Q_ω(x)−η`。

所有正式求解使用 Python 3.12.10、Pyomo 6.10.1、gurobipy/Gurobi 13.0.2、`gurobi_direct`、Threads=1，并先通过 preflight；无 solver fallback。

## 3. MP、LB、UB

第 r 次 MP 使用 S_r：

    min c(x)+η
    s.t. Stage 1 constraints,
         scenario recourse and c(x)+E_ω≤B, ∀ω∈S_r,
         η≥E_ω+Σ_i s_i u_iω, ∀ω∈S_r.

有效 MP bound 产生 LB。对 MP 解 x_r，只有完整 exact oracle 得到的 `c(x_r)+max_ωQ_ω(x_r)` 才是正式 global UB candidate。维护历史最大有效 LB 与最小完整-oracle UB。Memory/candidate 命中只可加入场景，不能更新正式 UB。

## 4. 收敛

仅当刚完成 Phase III/完整 exact oracle，且 global gap 与最大场景 violation 同时满足冻结绝对/相对容差，才可返回 optimal。最大迭代、时限、非有限值、MP/oracle 非最优或重复违反场景无法推进均返回显式非收敛状态。

## 5. A0 — Standard C&CG

1. 用预注册、与结果无关的规则选择初始场景。
2. 求 MP 并更新 LB。
3. 每轮调用完整 exact oracle，更新 UB。
4. 若精确收敛条件成立则停止；否则加入 canonical 最坏场景并继续。

A0 是精确 baseline。

## 6. A1 — Memory-Guided Three-Phase C&CG

“Three-Phase”只指算法搜索流程，不表示多阶段鲁棒优化；模型仍是两阶段。

### Phase I — Memory inspection

按冻结顺序检查合法 memory 场景，并以当前 x 精确评价。若发现 violation，记录来源并加入 MP；不能更新正式 UB 或认证收敛。

### Phase II — Candidate search

在冻结规则生成的较小候选集合中搜索当前解的违反场景。命中只加入 MP；候选集无违反不能宣告收敛。

### Phase III — Full exact certification

仅当 I/II 均未发现违反时，对完整 Ω 调用 exact oracle。只有 Phase III 可以更新正式 UB、证明无遗漏场景并认证最终收敛。

## 7. A1 在 N5 前冻结的内容

具体 scoring 公式/权重、candidate set 生成与评价预算、memory 合法来源/更新/容量/淘汰/清空/跨实例边界、tie-break 和状态机伪代码在进入 N5 前冻结。未冻结时默认禁止跨实例 memory。N6 pilot 只验证运行和资源规模，不得选择或修改算法。

## 8. 与旧 SPW-C&CG 的边界

| 维度 | 旧 SPW-C&CG | 新 A1 |
|---|---|---|
| 状态 | 跨预算迁移 active/history 场景形成初始池 | MP、memory、candidate、certification epoch 分离 |
| 记忆来源 | 较低预算实例的最终活跃/对抗场景 | N5 前冻结的合法历史；validation/OOS/formal 反馈禁止 |
| 候选规则 | 无独立 Phase II scoring | 必须有可复现 candidate generation/scoring |
| oracle 触发 | 每轮完整 oracle | I/II 无违反后才触发 Phase III |
| 场景来源 | 初始迁移或 oracle | 分别记录 memory/candidate/full-oracle 来源 |
| 认证 | 完整 oracle | 仍仅完整 Phase III oracle |

若 N5 冻结后的状态机不能实质超过旧机制，只能降格为工程变体，不能靠改名宣称创新。

## 9. 正确性不变量

场景必须属于同一 Ω；LB 只来自有效 MP；UB 只来自完整 oracle；approximate hit 只加场景；重复场景有序去重；并列最坏场景按 canonical ID；最终解绑定 Phase III 证据；M2(y_F=0)=M1 与 M1(base)=M0 在 EF/A0/A1 中均成立。

## 10. 指标与验收

记录 objective、LB/UB/gap、termination、total/MP/oracle/pool time、exact oracle calls、scenario evaluations、iterations、pool size、phase hits、scenario IDs、环境/config/instance/code hash。

### N4 入口门槛

进入 N4 前冻结 E1 正确性验收标准：EF/A0 目标一致性的绝对与相对容差、C&CG global gap 与 scenario violation 接受标准、solver optimality/非最优状态接受规则、A0 初始场景规则及 canonical worst-scenario tie-break。N4 使用这些标准完成 EF=A0，不得在得到结果后修改。

### N5 入口门槛

进入 N5 前冻结 A1 scoring、candidate generation/evaluation budget、memory 生命周期、完整状态机、Phase III 触发规则和 tie-break。N5 以 N4 已冻结的正确性标准补齐 EF=A0=A1、小型手工最坏场景、无漏认证、失败传播和确定性重放。

### N6/N7 边界

进入 N6 前登记 pilot 专用参数、pilot seeds、运行时限和最大迭代，仅验证 execution readiness。N7 冻结 E2–E6 正式科学参数、运行规则、失败统计和统计推断，但不得重新定义 N4/N5 已冻结并使用的正确性标准或 A1 状态机。

N2–N5 development/test fixtures、N6 pilot configuration、N7 formal scientific parameters 三类严格分离；前两类不得因结果表现自动升级。A1 冻结后不因速度不足创建 A2/A3/A4；允许 overhead 和负加速。
