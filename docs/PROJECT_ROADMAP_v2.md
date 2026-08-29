# PROJECT ROADMAP v2 — Active Q-F-R roadmap

状态：R0 与 R1 已完成、通过独立复审并人工合并。R2 尚未启动，当前仅为 `READY_FOR_EXPLICIT_R2_AUTHORIZATION`；本路线图同步不构成 R2 或任何后续阶段的自动启动授权。

## 1. 当前状态与设计权威

R0 已将用户确认的异质物资 Q-F-R 两阶段鲁棒设计冻结并落入仓库。其状态为：

`COMPLETED / INDEPENDENT REVIEW PASSED / MERGED`

当前数学规范为 [MODEL_SPEC_v2.md](MODEL_SPEC_v2.md)，研究问题和证据链为 [RESEARCH_DESIGN_v2.md](RESEARCH_DESIGN_v2.md)，算法方向为 [ALGORITHM_DIRECTION_v2.md](ALGORITHM_DIRECTION_v2.md)，历史与重设计追溯见 [REDESIGN_TRACEABILITY_v2.md](REDESIGN_TRACEABILITY_v2.md)。这些 R0 scientific definitions 已冻结；固定总预算下的异质物资 Q-F-R 两阶段鲁棒设计不因本次治理同步而改变。

R1 `Legacy Reuse & Impact Audit` 已完成 157 个 tracked paths 的审计、独立复审和人工合并。其状态为：

`COMPLETED / INDEPENDENT REVIEW PASSED / MERGED`

R1 的正式分类保持不变：39 `DIRECT_REUSE`、29 `REUSE_WITH_MODIFICATION`、85 `HISTORICAL_ONLY`、4 `REWRITE_REQUIRED`。分类权威与实施边界见 [LEGACY_REUSE_AUDIT_v2.md](LEGACY_REUSE_AUDIT_v2.md) 和 [IMPLEMENTATION_IMPACT_MAP_v2.md](IMPLEMENTATION_IMPACT_MAP_v2.md)。本路线图不得重新解释或改变这些分类。

v1 和 N0–N7-pre 属于 old-route historical design/evidence。它们必须保留用于历史、审计和工程回归，但不能证明 Q-F-R v2 的模型或算法正确性。PR #10 提供的通用工程 hardening 继续保留。

## 2. R0–R8 active route

各阶段严格按依赖顺序推进。每个尚未完成的阶段都必须由用户显式授权启动，并在完成实施、自检、Draft PR、独立复审、同 PR 修复与复审后，等待用户人工批准合并；不得自动 merge，也不得自动进入下一阶段。

| 阶段 | 正式名称 | 当前状态 | 阶段范围与进入下一阶段的门禁 |
| --- | --- | --- | --- |
| R0 | Research Redesign Freeze | `COMPLETED / INDEPENDENT REVIEW PASSED / MERGED` | 已冻结 research question、Q/F/R 定义、异质物资结构、M0/M1/M2、固定总预算、F-R 机制和 finite-scenario robust framework。 |
| R1 | Legacy Reuse & Impact Audit | `COMPLETED / INDEPENDENT REVIEW PASSED / MERGED` | 已完成 legacy asset 分类与 implementation impact map；旧科学机制和证据不进入 v2 active scientific path。 |
| R2 | New M0/M1/M2 Implementation | `READY_FOR_EXPLICIT_R2_AUTHORIZATION` | 仅实现新模型、programmatic nesting 与 model-level validation/tests；必须由用户显式授权后才能启动。 |
| R3 | EF + Standard C&CG Correctness | `NOT_STARTED / NOT_AUTHORIZED` | 实现 EF 与 A0 Standard C&CG，建立新路线 `EF ≈ A0` correctness evidence。 |
| R4 | Improved C&CG + Correctness | `NOT_STARTED / NOT_AUTHORIZED` | 先冻结 A1_new，再实现并建立 `EF ≈ A0 ≈ A1_new` correctness evidence；旧 A1 不自动继承。 |
| R5 | Pilot & Mechanism Diagnosis | `NOT_STARTED / NOT_AUTHORIZED` | 预注册 pilot，诊断 Q/F/R 响应、参数区间、runtime 与结构性退化；不得为机制激活而事后调参。 |
| R6 | Formal Experiment Design Freeze | `NOT_STARTED / NOT_AUTHORIZED` | 仅在 pilot 后冻结正式 budgets、seeds、scenario counts、scale definitions、sensitivities、repetitions、OOS sizes 与统计方案。 |
| R7 | Formal Experiments | `NOT_STARTED / NOT_AUTHORIZED` | 按冻结设计执行正式实验，保存完整 source/config/status/raw evidence 与失败结果。 |
| R8 | Results & Paper Evidence | `NOT_STARTED / NOT_AUTHORIZED` | 汇总 scientific、correctness 与 algorithm 三条证据链，形成可审计结果和论文证据；novelty wording 仍须专门治理。 |

A1_new 的最终机制与名称尚未冻结。正式实验的预算、seed、场景数、OOS 样本数、重复次数和规模阈值均尚未冻结；旧协议、旧默认值和 pilot 数值不得自动升级为正式设计。

## 3. R2 implementation boundary

R2 当前仅为 `READY_FOR_EXPLICIT_R2_AUTHORIZATION`，不是 `R2_STARTED`。用户显式授权 R2 后，其范围仅包括：

- v2 model data/schema adaptation；
- heterogeneous multi-item support；
- scenario representation `(d_iω, δ_iω)`；
- M0 = Q；
- M1 = Q+F；
- M2 = Q+F+R；
- programmatic nesting：M1 在 F=0 时退化为 M0，M2 仅允许 base reliability level `r=0` 时退化为 M1；
- model-level validation/tests，包括定义域、多物资平衡、成本与固定总预算会计。

R2 不负责：

- EF；
- A0 Standard C&CG；
- A1_new；
- pilot；
- formal experiment design；
- scientific experiment execution。

R2 不得选择未来阶段的正式参数、scenario distributions、seeds、规模档、OOS sizes、重复次数、统计阈值或 A1_new 机制。实施必须遵守 R1 的正式分类：保留 historical paths，复用已审核的通用工程基础设施，并为 v2 scientific path 建立明确、版本化的新实现。

## 4. 冻结时序与证据原则

1. 新数据与模型测试使用的 development fixtures 必须登记为非正式参数，遵守冻结的生产定义域，不得成为正式科学参数。
2. R3 进行 EF/A0 正确性比较前，必须冻结新路线的 correctness protocol、容差、gap/violation、精确状态接受规则、初始场景及必要的并列解处理。
3. R4 实现 A1_new 前，必须完成专门机制设计与独立复审；不得默认沿用 old Memory、ranking、candidate score 或 three-phase mechanism。
4. R5 pilot 前，必须登记 pilot 参数、seed、规模、限制、停止规则、计时和 audit，并先固定 source/protocol/config 再观察结果。
5. R5 完成后、R7 正式运行前，必须在 R6 冻结正式预算网格、参数标定、scenario generation、train/test sizes、seed registry、规模档、timing/OOS repetitions、失败统计与推断方案。

不得事后重定义已经使用的正确性标准来让结果通过。Development/pilot 参数不得因为表现好而自动升级为 formal；不得利用旧 N7-pre 失败或新 pilot 结果进行“调到机制激活”的循环。若发现真正的数学或科学错误，必须停止并通过正式 redesign governance 重新打开相关定义。

## 5. 实验、OOS 与规模原则

三条证据链必须分离：model correctness、scientific/managerial findings、algorithm performance。M0→M1→M2 比较用于识别机制增量价值；B、h、a、需求风险、δ、F/R 成本及 η 的分析始终围绕冻结的统一 Q-F-R 模型。

正式科学实验必须包含异质多物资并体现三类代表性特征，不能继续以 `|I|=1` 作为全部正式范围。Small 用于 EF/A0/A1_new correctness，medium 用于主要性能比较，large 用于 scalability/stress；当 EF 在较大规模不可执行时，可仅比较 A0/A1_new。各档物资数、场景数和 runtime limits 尚未冻结。

Independent OOS evaluation 使用独立的 `Ω_test`：固定训练得到的 first-stage strategy `Q*, F*, R*`，只允许 second-stage `x, u` 响应。评价必须覆盖 shortage、recourse cost、total cost、budget feasibility、F fulfillment 和 worst/tail performance。测试集不是 uncertainty set，不得用于重新选择第一阶段策略或挑选参数。

## 6. PR、审计与停止规则

- 每个主要阶段原则上对应一个有意义的 Draft PR；阶段内修复回到同一 PR，不按模块、seed 或单次 run 拆分。
- 完成阶段后停止并等待独立复审；不自动 merge，不自动进入下一阶段。
- 代码、配置、协议、commit/tree、环境、状态与原始输出必须可追溯；复用通用工程工具不能复用旧 scientific evidence 充当 v2 证据。
- 保存失败、首次异常与非激活结果；不得覆盖、删除、换 seed、事后调容差或悄悄扩大范围。
- 科学参数或算法结构变更必须显式说明原因并重新验证；旧证据只覆盖其原 source、定义和阶段。
- 若发现模型矛盾、正确性错误、evidence-integrity 问题或未冻结的科学选择，必须停止相关执行并请求治理决定，不以工程测试通过代替科学正确性。

本次 active-roadmap synchronization 只更新项目治理状态。它不修改 R0 scientific definitions，不修改 R1 classifications，不实现模型或算法，不执行 scientific/solver runs，也不授权启动 R2。
