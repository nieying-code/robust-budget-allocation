# EXPERIMENT PLAN v1

状态：N0 最终实验结构；仅设计，不运行 pilot 或正式实验。

## 1. 共同协议

- 三模型使用同一实例、有限 Ω、需求、所有 Reliability 等级履约数据和应急价格数据。
- 唯一主目标为 T-COST；服务水平、CVaR、缺货量、未使用资源 h 和 unused budget 只作评价指标。
- development、pilot、formal training、validation、OOS test seeds 分离且集合不相交。
- 每个 run 绑定 code commit/tree、config、instance/scenario、environment 和 seed hash；formal 不覆盖，失败写终态。
- 正式求解仅用锁定 Gurobi 环境，无 fallback。

## 2. E1 — 正确性证据（N4/N5）

N4 用手算微型实例和可完整枚举小实例验证 Extensive Form=A0；N5 补齐 Extensive Form=A0=A1。覆盖单/多场景、基础/高 Reliability、y_F=0/1、Option 不值得购买、预算紧/松、应急额度或剩余预算绑定、缺货、h>0、并列最坏场景和两个嵌套退化。

比较 objective、Stage 1 解（允许多解规则）、场景 recourse、预算、最坏场景与 LB/UB。E1 完成后冻结为 correctness evidence；N8 只把它作为回归门槛，不重新包装为效果实验。

## 3. E2 — M0/M1/M2 机制消融

逻辑为 M0 → +Reliability → M1 → +F-OPTION → M2。M0/M1 是消融模型，不与 M2 比赛优劣。

- M0→M1：识别供应商级离散 Reliability 的增量作用。
- M1→M2：识别灾前付费购买未来应急采购权的增量作用。

报告 T-COST、C_Q/C_R/K_F/E、预算份额、unused budget、Reliability 选择、y_F、缺货、服务、h 和最坏场景。允许基础等级、y_F=0、M2=M1、花满/不花满预算、h>0；均不是失败。

## 4. E3 — M2 风险敏感性

围绕论文主模型 M2，按预注册单因素或可识别 factorial 设计改变需求风险、履约风险、相关性或不确定集压力，研究 Quantity/Reliability/Option 配置和最坏经济损失如何变化。风险范围与场景生成公式在 N7 冻结；不复用旧 C0/C1/T03、beta 或种子。

## 5. E4 — M2 预算与机制敏感性

在固定风险结构下改变 B，并按预注册设计考察 Reliability premium、K_F 与 F_bar。报告配置断点、Option 购买区间、剩余灾后现金、缺货、h 和目标变化。预算网格与机制参数值在 N7 冻结；不因观察到零选择而调参。

## 6. E5 — M2 样本外评价

训练场景只求策略；独立测试场景只评价，禁止测试集重优化或筛选策略。主要评价 M2 在独立需求、履约和应急价格下的平均经济损失、CVaR95、缺货、服务水平、实际 E、unused budget 与 h。为解释机制可带入冻结的 M0/M1 嵌套策略作为参照，但不改变 M2 主分析定位。

使用 common random numbers 和独立 training–test seed pair；效应、置信区间、多重比较和失败规则在 N7 预注册。简单固定策略不是默认强制矩阵，只有 N7 明确批准才加入。

## 7. E6 — A0 vs A1 性能

使用同一模型（以 M2 为主）、实例、Ω、初始场景规则、T-COST、容差、硬件、Threads 和完整 oracle。报告 objective consistency、total/MP/oracle/pool time、exact oracle calls、scenario evaluations、iterations、pool size、scalability 和 termination。

主比较只要求 A0 vs full A1。memory-only/candidate-only 是可选次要消融，须在 N7 判定确有识别必要且计算可控才加入。A1 结果允许更慢；不得据此发明 A2/A3/A4。

## 8. Pilot 与正式门槛

N6 pilot 只验证已冻结模型/算法的运行、容量、时限、字段和失败处理，不证明效应，不选择 A1 scoring。N7 冻结参数值、生成器、规模矩阵、seeds、指标、统计、容差、停止规则和正式授权。N8 先通过 E1 回归门槛，再执行 E2–E6。

## 9. 管理问题覆盖

- E2 回答 Reliability 与 Flexibility 的增量机制。
- E3 回答风险如何改变 M2 的 Q/R/F 配置。
- E4 回答预算、Option 与 Reliability 价格/能力如何改变配置。
- E5 回答 M2 的独立样本外经济与服务表现。
- E6 回答 Three-Phase memory/candidate search 是否在保持精确性的同时改善计算表现。

当前不生成 raw outputs，不声明任何实验效果。
