# RESEARCH DESIGN v1

状态：N0 最终设计；科学结构已关闭，等待 Draft PR #1 外部复审。日期：2026-08-26。

## 1. 研究问题

本项目研究单一固定全周期预算 B 应如何配置给三种功能不同的资源：灾前购买的 Quantity、提高常规供应履约能力的 Reliability，以及灾前付费购买、灾后按实际缺口行使的 Flexibility。核心问题是风险、预算与机制参数变化时三者的配置规律，不是证明 Reliability 或 Flexibility 必须为正。

候选论文题目：**Robust Budget Allocation among Quantity, Reliability, and Post-Uncertainty Flexibility: Models and Exact Memory-Guided Three-Phase C&CG**。

本项目是独立新研究。旧项目只提供 baseline、工程模式和 provenance；不继承其模型、场景公式、参数、种子、结果、审批或 Git 历史。

## 2. 冻结的科学结构

- 两阶段、单期、非易腐、无供应恢复。
- 不确定集为有限场景集 Ω；三模型使用同一实例、Ω、需求与履约数据。
- 所有真实现金支出来自同一个固定总预算 B，不设灾前/灾后分预算或外部应急资金。
- 预算采用 ≤B，允许未使用预算；unused budget 只是会计结果，不是 Flexibility。
- 唯一目标是最小化最坏情形总经济损失（T-COST）。服务水平、CVaR、缺货量和未使用资源只作评价指标。

## 3. 决策时序

Stage 1 在场景揭示前作不可逆决策：M0 选择 Quantity；M1 选择 Quantity 与供应商级离散 Reliability；M2 还决定是否购买标准应急采购权 y_F。

随后场景 ω 揭示需求、常规供应在各 Reliability 等级下的履约能力，以及 M2 的应急采购价格。

Stage 2：M0/M1 只进行到货资源分配并记录缺货与未使用资源；M2 若 y_F=1，可先按场景缺口进行有限应急采购，再完成同样的分配与记录。M0/M1 虽无灾后采购，仍因需求与履约在 Stage 2 才揭示而属于两阶段模型。

## 4. C1–C4 最终定义

### C1 — F-OPTION

Flexibility 是买/不买的标准应急采购权 y_F∈{0,1}。购买时灾前支付 K_F>0，并获得合同允许的最大灾后采购金额 F_bar>0。场景支出 E_ω=Σ_i p^F_iω g_iω 满足 E_ω≤F_bar y_F。F_bar 不是额外资金；实际支出仍受同一 B 约束。K_F 与 F_bar 的数值推迟到 N7 前按文献、数据或预注册标准化方案冻结。

### C2 — 无基础应急通道

M0/M1 没有灾后额外采购。M2 的 F-OPTION 是唯一灾后采购机制，因此不存在两条重复应急通道或外部融资。

### C3 — T-COST

统一目标为：

    min C_Q + C_R + K_F y_F + θ,
    θ ≥ E_ω + Σ_i s_i u_iω,  ∀ω∈Ω.

缺货损失进入经济目标但不进入现金预算。Option fee 与应急支出既是实际现金流，也分别进入灾前成本和场景补救成本。

### C4 — 有限离散、供应商级 Reliability

每个供应商 j 有任意有限等级集 K_j，并选择一个等级 z_jk。M0 固定基础等级 k=0；M1/M2 可付费选择其他等级。Reliability 只改变常规合同的场景履约能力，不改变需求、不创造预算、不等同于灾后 Flexibility。基础等级成本最低；更高等级保障成本不低；同一场景下更高等级履约能力不得更低。具体等级数、premium 与改善幅度留待 N7 前冻结。

## 5. M0、M1、M2

### M0 — Quantity Baseline

只决定灾前采购数量，Reliability 固定基础等级，Option 关闭；灾后只分配实际到货并记录缺货与未使用资源。它回答“固定预算下，只依靠灾前采购时应该买多少”。

### M1 — Quantity + Reliability

在 M0 上只增加供应商级离散 Reliability 决策，Option 关闭且无灾后采购。它回答“固定预算下，应该多买，还是提高既有供应的可靠性”。

### M2 — Full Model

论文主模型；灾前联合决定 Quantity、Reliability 与是否购买 F-OPTION，灾后若已购买则根据实际缺口进行有限应急采购。它回答“如何在提前拥有资源、提高供应可靠性和购买未来调整能力之间联合配置”。

必须程序化满足 M2(y_F=0)=M1、M1(base reliability)=M0。

## 6. 资源与预算闭合

场景相关未使用资源 h_iω≥0。每个物资满足：

    served_iω + shortage_iω = demand_iω,
    served_iω + h_iω = regular_delivered_iω + g_iω.

M0/M1 中 g_iω=0。首版没有持有、处置、过期成本或残值；Quantity 采购成本已进入目标。h 是重要管理指标。

每个 M2 场景满足：

    C_Q + C_R + K_F y_F + E_ω ≤ B.

M0/M1 相应令 y_F=0、E_ω=0。缺货 penalty 不进入现金预算。

## 7. 模型定位与消融

M0/M1 是机制消融，不与 M2 竞争“谁更好”：M0 → 加 Reliability → M1 → 加 Flexibility → M2。E2 分别识别 Reliability 与 Flexibility 的增量作用。允许基础 Reliability、y_F=0、M2=M1、花满或未花满预算、存在缺货或未使用资源；这些均不是模型失败。

E3–E5 的主要管理分析围绕 M2，研究风险、预算和机制参数改变时的 Q/R/F 配置及样本外表现。

## 8. 算法

A0 是每轮使用完整 exact oracle 的 Standard C&CG。A1 是 Memory-Guided Three-Phase C&CG：Phase I memory inspection，Phase II candidate search，Phase III full exact certification。只有 Phase III 完整 oracle 可以更新正式全局 UB 和认证最终收敛。

A1 scoring、memory 来源/更新/淘汰/跨实例边界和 candidate rule 在进入 N5 前冻结；N6 pilot 不得用于挑选或修改算法。

## 9. 研究原则与局限

不因 Reliability 选择基础等级、y_F=0、M2=M1、A1 更慢或管理结果不符合预期而修改设计。只有数学、经济、单位、重复计费、语义或 specification/代码不一致才允许修订。

首版局限：单期非易腐，不考虑库存持有、过期、处置、残值、多期动态或供应恢复；这些仅作为未来研究方向。

## 10. 阶段门槛

N0 七文件及其 repo 冻结副本进入单一 Draft PR #1。PR 未经用户复审并合并前，不进入 N1，不迁移旧代码，不实现模型/算法，不运行 pilot 或正式实验。

## 11. N0 最终一致性复审

| 检查项 | 结论 |
|---|---|
| Q/R/Option 重复计费 | PASS：基础采购、Reliability 增量成本、Option fee 分量互斥 |
| 应急支出进入预算与目标 | PASS：E_ω 各出现一次，分别承担预算可行性与经济成本作用 |
| 缺货 penalty 不进现金预算 | PASS |
| M2(y_F=0)=M1 | PASS：E=0 且正价格强制 g=0 |
| M1(base)=M0 | PASS：基础等级增量成本为零，履约与 M0 相同 |
| 三模型时间顺序 | PASS：共同 Stage 1—场景揭示—Stage 2 |
| 所有真实现金只受 B | PASS：无外部或分阶段预算 |
| h 物理平衡 | PASS：到货+应急量严格分为 served+h |
| 三模型公平使用 Ω | PASS：同一数据对象与场景 hash |
| A0/A1 对齐 T-COST | PASS：共同 c(x)、Q_ω、MP 与 exact oracle |
| E2–E6 回答预算管理问题 | PASS：机制、风险、预算、OOS 与计算性能完整覆盖 |

未发现 N0 数学或经济 blocker。
