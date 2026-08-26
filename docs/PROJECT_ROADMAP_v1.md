# PROJECT ROADMAP v1

## N0 — 研究设计（当前阶段）

- 输入：新研究要求、只读 legacy handoff、已确认 C1–C4。
- 工作：冻结两阶段单期非易腐有限场景模型、T-COST、M0/M1/M2、A0/A1、实验与治理边界；完成一致性审计。
- 交付：七份一致的 v1 文件、repo `docs/` 冻结副本、hash manifest、Draft PR #1。
- 验收：两处 hash 一致；CI/checks 完成；用户复审并决定是否合并。
- 禁止：PR #1 合并前进入 N1/N2 或以后阶段；不得迁移旧代码、实现模型/算法、运行 pilot/formal。

## N1 — 通用工程迁移

- 输入：已合并的 N0 PR、冻结 legacy provenance/reuse plan。
- 工作：只迁移并净化获准的环境、I/O、hash、统计、状态等通用能力。
- 交付：provenance manifest、通用模块及测试。
- 验收：逐文件来源可追溯；无旧科学 schema/config/seed/import。
- 禁止：整仓复制、迁移旧模型/场景/结果、提前实现 A1。

## N2 — M0

- 输入：冻结的 T-COST、预算、数据 schema 与场景结构。
- 工作：使用 development/test fixtures 实现 Quantity、基础 Reliability、Stage 2 分配/u/h 与 EF 手工实例；通用 I 接口允许，但当前科学范围为单物资。
- 交付：M0 builder、数学—代码映射与测试。
- 验收：预算、单位、平衡、场景与手算一致。
- 禁止：加入 Reliability 决策、Option 或基础应急采购。

## N3 — M1/M2

- 输入：M0 与冻结的离散供应商级 Reliability、F-OPTION。
- 工作：增加 z/q-level、y_F/g/E、场景预算与嵌套测试。
- 交付：M1/M2 builders 和机制测试。
- 验收：M2(y_F=0)=M1、M1(base)=M0；无重复计费；penalty 不进预算；h 平衡闭合。
- 禁止：因变量为零改变结构；加入现金储备、基础应急、易腐或恢复。

## N4 — Extensive Form + A0

- 输入：冻结模型 builder 与 exact recourse；进入 N4 前已冻结 E1 的目标一致性绝对/相对容差、C&CG gap/violation 标准、solver optimality 接受规则、A0 初始场景与 canonical tie-break。
- 工作：完整 EF、完整 finite-Ω oracle、Standard C&CG、bound/status 管理。
- 交付：E1 的 EF=A0 evidence。
- 验收：按入口前冻结标准验证目标/预算/最坏场景一致；仅 full oracle 产生 UB 和收敛认证。
- 禁止：A0 未通过前实现 A1。

## N5 — A1

- 输入：已验证 A0；在进入 N5 前冻结的 scoring、candidate、memory 生命周期、状态机和 Phase III 触发规则；继续使用 N4 冻结的 E1 标准。
- 工作：实现 Phase I memory、Phase II candidate、Phase III exact certification。
- 交付：A1 测试并补齐 E1 的 EF=A0=A1。
- 验收：每次收敛绑定 Phase III；确定性重放；与旧 SPW 边界成立。
- 禁止：用 N6 pilot 选 scoring；因速度弱创建 A2/A3/A4。

## N6 — Pilot

- 输入：冻结模型/算法；进入 N6 前已登记的 pilot 专用参数、pilot seeds、运行时限和最大迭代。
- 工作：只验证正确性、计算量、时限、字段和失败处理。
- 交付：pilot report、计算预算和参数可辨识性清单。
- 验收：无 correctness blocker；计算规模、稳定性和 execution readiness 达标。
- 禁止：把 pilot 当效果证据或修改核心结构/A1 定义。

## N7 — 实验设计冻结

- 输入：N6 报告、文献/数据/标准化依据。
- 工作：冻结单物资 E2–E6 的 Reliability 等级数/费用/履约改善、K_F、F_bar、风险范围、预算网格、Ω、formal/validation/OOS seeds、正式运行规则、失败统计、统计推断与授权。
- 交付：哈希 protocol、machine-readable configs、formal authorization。
- 验收：seed 隔离、审计测试和资源门槛通过。
- 禁止：重新定义 N4/N5 已冻结并使用的正确性标准或 A1 状态机；禁止正式结果后修改参数或门槛。

## N8 — 正式实验

- 输入：冻结协议、授权、clean source、通过 preflight。
- 工作：先运行 E1 回归，再执行 E2–E6；保存不可变证据。
- 交付：raw runs、compact audit、projection 和失败清单。
- 验收：计数/hash/provenance 闭合，不选择性删除结果。
- 禁止：覆盖、补跑有利 seeds、测试集重优化、solver fallback。

## N9 — 论文结果整理

- 输入：冻结正式证据。
- 工作：统计、图表、正负结果、局限与可复现附录。
- 交付：论文结果包和草稿。
- 验收：所有数值可追溯，主张与证据一致。
- 禁止：为叙事回改模型、算法或实验。

## PR 治理

- 每个主要阶段原则上一个 Draft PR；阶段内修复继续提交原 PR。
- N0 使用唯一 Draft PR #1：`Freeze N0 Research Design v1`。
- Codex 不自动 merge；阶段完成后停止并等待用户复审。
- Pilot/formal 不按单个 seed 创建 PR；代码/协议按阶段 PR，制品按 artifact protocol。
- PR #1 合并前，N1 及所有后续阶段均处于硬禁止状态。

## 参数与科学范围治理

- N2–N5 只使用 development/test fixtures；N6 只使用登记的 pilot configuration；N7 才冻结供 N8 使用的 formal scientific parameters。
- Development 与 pilot 参数不得因结果表现自动升级为 formal。
- E2–E6 正式科学实例固定 |I|=1；多物资不进入当前规模矩阵或论文核心创新。
