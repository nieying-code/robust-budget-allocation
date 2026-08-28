# RESEARCH DESIGN v2 — Q-F-R redesign

状态：R0 科学设计冻结稿，待本阶段 Draft PR 独立复审；仅文档，不是实现或实验结果。

## 1. 文档效力与研究范围

本套 v2 文件记录用户已经确认的新路线，作为后续 R1–R8 的科学设计基线；R0 PR 合并前不授权任何后续阶段。数学定义以 [MODEL_SPEC_v2.md](MODEL_SPEC_v2.md) 为准，算法方向见 [ALGORITHM_DIRECTION_v2.md](ALGORITHM_DIRECTION_v2.md)，历史边界见 [REDESIGN_TRACEABILITY_v2.md](REDESIGN_TRACEABILITY_v2.md)，阶段门槛见 [PROJECT_ROADMAP_v2.md](PROJECT_ROADMAP_v2.md)。这五份文件共同构成新路线设计，不自动继承 v1 中未重述的科学或实验约束。

v1 文档、已存在的模型代码及旧正确性证据全部保留为历史；它们不是新模型的实现或认证。新路线正式科学主实验必须包含多种异质物资，覆盖普通、保鲜型和易腐型三类代表性物资，不能退回单物资主实验。具体物资数和参数标定不在 R0 冻结。

研究主题是“异质性应急物资的两阶段鲁棒预算配置：考虑 Q-F-R 联动”；这是研究范围描述，不是最终论文标题。

## 2. 核心问题和机制链

在一个固定全周期总预算 B 下，面对物资储存/保鲜/易腐特征差异、灾后需求不确定性和柔性供应受损风险，管理者应在灾前将多少资源用于实体储备、柔性能力预留及其可靠性保障，以平衡灾前真实支出、灾后实际采购/生产支出与最坏场景缺货损失？

| 机制 | 灾前含义 | 经济作用 |
| --- | --- | --- |
| Q | physical prepositioning，实体物资储备 | 提前实体化 |
| F | reservation of flexible post-disaster supply/production capacity | 延迟实体化，先付费获得可用能力 |
| R | reliability protection for F fulfillment | 保障延迟实体化的兑现能力 |

候选研究机制链为：

heterogeneous material characteristics → Q-F tradeoff → post-disaster flexible-supply disruption → F-R tradeoff → joint Q-F-R allocation under one fixed total budget。

Q-F-R 是经济机制链，不是三个时间阶段。所有模型都是 two-stage robust optimization：

1. Stage 1：灾前联合决定 Q、F 及 F 的可靠性等级；决策不可根据灾后场景改变。
2. 需求 d 与柔性供应损失 δ 揭示。
3. Stage 2：决定实际柔性采购/生产 x 和缺货 u；不得重新选择灾前 Q、F、R。

## 3. 用统一模型表达物资异质性

用 h_i 表示单位物资单位时间的储存/保鲜负担，用 a_i 表示灾害发生时有效留存比例，用外生 τ 表示规划/等待期。

| 代表类别 | h_i | a_i | 含义 |
| --- | --- | --- | --- |
| Ordinary goods | 较低 | 较高 | 储存负担和变质风险较低 |
| Preservation-sensitive goods | 较高 | 相对较高 | 冷链、温控等投入增加长期储存成本 |
| Perishable goods | 低至中等 | 较低 | 等待期间更明显的失效、过期或有效数量损失 |

这些是解释性特征，不是三套模型、数值分组阈值或 h 与 a 的函数关系。灾前实体成本和灾时有效储备分别是：

$
C_Q=\sum_i(c_i^Q+h_i\tau)Q_i,\qquad Q_i^{eff}=a_iQ_i.
$

初版不增加独立的 $w_i(1-a_i)Q_i$ spoilage cost；有效数量损失已经通过 a_i 影响可用储备。h_i τ 是储存服务的真实支出，不是对同一损失再加罚金。R0 不设库存轮换、补货、动态变质、库龄追踪或多期库存动态，也不规定 a_i 随 τ 变化的函数。

## 4. 柔性能力与可靠性

每个物资采用一个代表性柔性供应/生产通道。F 是灾前付费预留的连续能力，x 是灾后实际使用量。物资内选择一个可靠性等级 r∈{0,1,2}，使用 F_ir 与二元 z_ir 的线性联结；最多选一个等级，允许不预留。

名义可预留能力上限 $\bar F_i$ 是物理/合同能力界限，不是随意设置的技术 Big-M。为抵消兑现损失，F_i 可以超过最大需求；不加入一般性的 F_i≤最大需求约束。

R 可解释为设施加固、备用电力、原料保障或运输保障，但只保护 F 的兑现，不保护 Q、不改变需求或场景概率、不增加预算。最高等级仍有残余风险：

$
\eta_{i0}=0<\eta_{i1}<\eta_{i2}<1,\quad
\rho_{i\omega}^{r}=1-(1-\eta_{ir})\delta_{i\omega}.
$

δ=0 时所有等级兑现比例均为 1，R 不创造能力；F=0 时 R 没有独立经济价值。费用是按预留能力计收的 reservation cost 和 reliability premium，没有额外固定可靠性费。无 supplier selection、multi-sourcing、相关供应商组合或跨物资柔性能力转移。

新 F 是 capacity reservation；旧路线的二元 F-OPTION、y_F 和 K_F 仅作为历史术语保留在追溯说明中，不属于 v2 模型。

## 5. 同一预算与唯一目标

$
\begin{aligned}
C_F&=\sum_{i,r}c_i^F F_{ir},& C_R&=\sum_{i,r}c_{ir}^R F_{ir},\\
C_\omega^E&=\sum_i p_i^F x_{i\omega},& L_\omega^S&=\sum_i s_i u_{i\omega}.
\end{aligned}
$

每个场景的真实支出满足：

$
C_Q+C_F+C_R+C_\omega^E\le B.
$

只有一个全周期 B，没有灾后额外资金，也不强迫花满预算。Reservation 为 capacity availability 付费；exercise 为实际生产/采购付费，两者不是重复计费。缺货损失是经济/社会损失，不是现金，不进入预算。

唯一主目标：

$
\min\ C_Q+C_F+C_R+\theta,\qquad
\theta\ge C_\omega^E+L_\omega^S\quad\forall\omega.
$

不加残值、处置成本或剩余物资罚金。配置为零、某等级不被选择、预算未花满或嵌套模型目标相同均是允许结果；不得以强制激活机制代替科学检验。

## 6. 三个嵌套模型与增量价值

| 模型 | 灾前决策 | 灾后决策 | 机制问题 |
| --- | --- | --- | --- |
| M0 — Q | 实体储备 Q | 缺货 u；x=0 | 仅提前实体化的预算配置 |
| M1 — Q+F | Q 与基础等级柔性能力 F | x、u | 延迟实体化的增量价值 |
| M2 — Q+F+R | Q、F 和等级选择 | x、u | 保障柔性兑现的增量价值 |

$
M1\big|_{F=0}=M0,\qquad M2\big|_{\mathcal R=\{0\}}=M1.
$

M2 是完整主模型，M0/M1 是机制消融，不是为得出某模型必胜而设置的竞争者。三模型在相同物资、场景、需求、基础损失数据、预算和成本口径下比较。后续必须以新模型程序化测试验证退化关系；旧路线的退化测试不能代替它们。

## 7. 不确定性边界

采用 finite scenario-based robust optimization：

$
\mathcal U=\{(d_\omega,\delta_\omega):\omega\in\Omega\}.
$

不确定性是需求 d 与柔性供应中断 δ；p_i^F 在本基线中是非场景相关的单位行使成本。Baseline does not explicitly model their correlation, so that demand-risk and supply-disruption effects can be separately identified. 这是建模边界，不是断言现实中的需求与中断独立，也不是已经建立因果识别结论。

不加入 Γ_D/Γ_S、budgeted uncertainty sets、Wasserstein/moment ambiguity、DRO、概率加权随机规划目标或显式需求—中断相关模型。不引入共同潜在灾害强度、copula、相关参数或联合分布估计。未来扩展须有科学理由和新的治理批准。

## 8. 三条独立证据链

| 证据链 | 必须回答的问题 | 不能替代的证据 |
| --- | --- | --- |
| 1. Model correctness | 新 M0/M1/M2 退化、会计和 EF≈C&CG 是否正确 | 旧 N6 结果和 OOS 不能代替新模型正确性 |
| 2. Scientific / managerial findings | B、h、a、需求风险、δ、F/R 成本及 η 如何影响配置；M0→M1→M2 的增量价值 | 参数化实例的正确求解不是管理规律证明 |
| 3. Algorithm performance | 随物资数、场景数和规模变化的 runtime、iterations、oracle workload、convergence | 更低模型目标不是算法提速证据 |

算法研究顺序为 EF→A0 Standard C&CG→A1 Improved C&CG。最终 A1 改进机制在 R0 不冻结，旧 Memory/Candidate 三阶段方案不自动继承；Standard C&CG 本身不是论文算法创新。

## 9. OOS 和计算规模原则

Independent OOS：$\Omega_{train}\to(Q^*,F^*,R^*)\to\Omega_{test}$。固定第一阶段（含等级选择及分等级能力），只允许 x、u 对未见场景响应，同样受一个全周期预算约束。未来至少评价缺货、recourse cost、total cost、budget feasibility、F fulfillment 和 worst-case/tail performance。OOS 主要支持证据链 2，不替代证据链 1。

| 规模档 | 用途 |
| --- | --- |
| small | 正确性，EF vs A0 vs 最终 A1 |
| medium | 主要算法性能比较 |
| large | scalability/stress；若 EF 不可执行，可只比较 A0 vs A1，并如实报告 EF 限制 |

原则已冻结，数值没有冻结：物资数、场景数、训练/测试规模、seed 数、OOS 重复次数、各档阈值及 timing repetitions 均须在后续 pilot 后确定。正式科学主实验必须体现多物资异质性；微型测试不能替代它。

## 10. 创新定位与尚未冻结事项

R0 仅冻结第 2 节的候选创新结构。已知相邻研究方向包括实体储备与产能储备、产能存活能力、原料中断、DRO 应急预置、易腐救援库存和灾前加固；这里只记录用户确认的定位边界，不声称完成了新的文献综述。

不得使用 first Q+F、first capacity reservation、first perishable relief、first reliability protection、first C&CG application 或 first-ever Q-F-R 等断言。最终 novelty wording：**NOT FROZEN AT R0**；需要后续专门 literature-positioning review。

以下不在 R0 确定：正式预算档、参数数值标定、seed 值及数量、场景数、train/test sizes、规模档数值、timing/OOS repetitions、最终 A1 机制与 ranking/memory 设计、统计显著性阈值、最终创新措辞和论文标题。Development、pilot 与 formal 参数用途必须分离，不能因旧或新诊断结果好看而自动升级为正式参数。

R0 的产物仅是设计文件和静态一致性检查，不产生新模型正确性、机制激活或算法优势的实证结论。
