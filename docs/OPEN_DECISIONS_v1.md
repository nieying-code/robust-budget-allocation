# OPEN DECISIONS v1

状态：N0 核心科学决策已关闭。以下仅为后续阶段按时点冻结的参数与算法实现事项，不是 N0 blocker，不得改变已通过结构。

## 1. 已关闭的科学范围

- F-OPTION；无基础应急；T-COST；有限离散供应商级 Reliability。
- 两阶段、单期、非易腐、无供应恢复、有限 Ω、统一预算 ≤B。
- M2 是主模型，M0/M1 是严格嵌套消融。
- 数学和接口可保留一般 I；首版 E2–E6 与论文科学主张固定 |I|=1，多物资仅为未来扩展。

除非发现真实数学、经济、单位或一致性错误，不得因 development、pilot 或正式结果重新打开这些科学设计。

## 2. 进入 N4 前冻结的 E1 标准

- 目标一致性绝对与相对容差。
- C&CG global gap 与 scenario violation 接受标准。
- solver optimality、time limit 和其他非最优状态的接受/拒绝规则。
- A0 初始场景规则与 canonical worst-scenario tie-break。

这些标准一经用于 N4/N5 正确性验证，N7 不得重定义。

## 3. 进入 N5 前冻结的 A1 定义

- candidate scoring 的公式、特征、归一化、权重和评价预算。
- candidate set 的生成、排序、去重和 tie-break。
- memory 的合法来源、字段、更新、容量、淘汰和清空规则。
- 是否允许跨实例 memory；未确认前默认禁止。
- Phase I/II 加入场景的批量规则。
- 完整状态机与 Phase III 触发条件。

Phase I/II 永远不能更新正式 UB 或认证收敛。N6 pilot 不得选择或改变上述定义。

## 4. 进入 N6 前登记的 pilot configuration

- pilot 专用模型/实例参数与规模点。
- pilot seeds。
- pilot 运行时限、最大迭代和 execution-readiness 门槛。

Pilot 只验证计算规模、稳定性和执行能力，不作为正式科学参数。

## 5. N7 冻结的 formal scientific parameters

- Reliability 等级数、固定保障费、单位 premium 与履约改善。
- K_F、F_bar、基础采购价、应急价格与缺货经济损失。
- 单物资需求/履约/应急价格联合场景、风险范围与 Ω 规模。
- 预算网格、机制敏感性网格及沿供应商/等级/场景维度的规模矩阵。
- formal、validation、OOS seeds。
- E2–E6 正式运行规则、时限/资源规则、失败统计、指标与统计推断方案。

这些值依据文献、数据或预注册标准化方案确定，不得为得到正 Reliability、正 Option 或预期加速而选择。N7 不得覆盖第 2–3 节已冻结的正确性标准或 A1 状态机。

## 6. 三类参数用途隔离

- N2–N5 development/test fixtures：代码、手算实例、正确性与异常路径测试专用。
- N6 pilot configuration：execution readiness 专用。
- N7 formal scientific parameters：冻结后供 N8 正式实验使用。

Development/test fixtures 与 pilot configuration 不得因结果表现自动升级为 formal scientific parameters。

## 7. N7 可选但非强制的次要实验

- memory-only、candidate-only 组件消融。
- 简单固定策略 baseline。
- Reliability 等级数的额外敏感性。

只有在科学识别必要、计算量可控且正式结果出现前预注册时才加入；不自动扩张 E2–E6。

## 8. 治理状态

N0 没有未决核心科学 blocker。所有收尾修订继续进入现有 Draft PR #1；PR 未由用户批准并合并前，禁止 N1 及后续工作。
