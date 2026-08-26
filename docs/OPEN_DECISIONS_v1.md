# OPEN DECISIONS v1

状态：N0 核心科学决策已关闭。以下仅为后续阶段的参数化与算法实现决策，不是 N0 blocker，也不得改变冻结结构。

## 1. 已关闭，不得重开为候选

- Flexibility：F-OPTION，二元 y_F，固定 K_F，合同金额上限 F_bar，实际 E_ω 与所有灾前支出共享 B。
- 基础应急：删除；M0/M1 无灾后采购，M2 Option 是唯一灾后采购通道。
- 目标：T-COST；缺货 penalty 进目标、不进现金预算。
- Reliability：任意有限离散等级、供应商级；成本与同场景履约能力随等级弱单调。
- 两阶段、单期、非易腐、无供应恢复、有限 Ω、预算 ≤B。
- M2 是主模型；M0/M1 是严格嵌套的机制消融。

除非发现真实数学、经济、单位或一致性错误，不得因 pilot/正式结果重新打开已经关闭的 C1–C4，或改为基础应急、连续 Reliability、多期、易腐等未冻结结构。

## 2. N7 前冻结的模型与实验参数

- 每个供应商的具体 Reliability 等级数；不预设两级或三级。
- Reliability 固定保障费 a_jk、单位 premium π_ijk 及其标准化/数据来源。
- 各等级的履约改善数值 ρ_ijkω 与场景单调构造。
- Option fee K_F 与合同金额上限 F_bar。
- 基础采购价、应急价格、缺货经济损失和采购上限。
- 需求/履约/应急价格的联合有限场景生成公式、风险参数范围与 Ω 规模。
- 预算网格、机制敏感性网格和实例规模矩阵。
- development、pilot、formal、validation、OOS seeds。
- 目标一致性容差、C&CG 容差、时限、最大迭代与统计规则。

这些值依据文献、数据或预注册标准化方案确定；不得为了得到正 Reliability、正 Option 或预期速度结果而选择。

## 3. 进入 N5 前冻结的 A1 定义

- candidate scoring 的公式、特征、归一化、权重和评价预算。
- candidate set 的生成、排序、去重和 tie-break。
- memory 的合法来源、字段、更新、容量、淘汰和清空规则。
- 是否允许跨实例 memory；未确认前默认禁止。
- Phase I/II 命中时单次加入一个还是一批场景。
- 完整状态机与 Phase III 触发条件。

N6 pilot 不得用于挑选或改变这些定义。Phase I/II 永远不能更新正式 UB 或认证收敛。

## 4. N7 可选但非强制的次要实验

- memory-only、candidate-only 组件消融。
- 简单固定策略 baseline。
- Reliability 等级数的额外敏感性。

只有在科学识别必要、计算量可控且正式结果出现前预注册时才加入；不自动扩张 E2–E6。

## 5. 治理状态

N0 没有未决核心科学 blocker。七份冻结文档进入 Draft PR #1 后等待外部复审；PR 未由用户批准并合并前，禁止 N1 及后续工作。
