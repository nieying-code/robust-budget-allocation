# PROJECT ROADMAP v2 — Active Q-F-R roadmap

状态：R0–R5 与 Q-F-R availability/model revision 已完成、通过独立复审并人工合并。R6-A Formal Data Preparation 已完成独立复审；R6-B Formal Experiment Matrix Freeze 正在同一 Draft PR #18 中进行。R7 与正式科学优化尚未启动。

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
| R2 | New M0/M1/M2 Implementation | `COMPLETED / INDEPENDENT REVIEW PASSED / MERGED` | 已实现修订前 Q-F-R v2 模型、programmatic nesting 与 model-level validation/tests。 |
| R3 | EF + Standard C&CG Correctness | `COMPLETED / INDEPENDENT REVIEW PASSED / MERGED` | 已对修订前模型建立 EF、A0 与 `EF ≈ A0` correctness evidence。 |
| R4 | Improved C&CG + Correctness | `COMPLETED / INDEPENDENT REVIEW PASSED / MERGED` | 已实现并验证修订前模型的 A1，建立 `EF ≈ A0 ≈ A1` evidence；PR #15 已人工合并。 |
| Q-F-R availability/model revision | Scientific/model revision + EF/A0/A1 correctness regression | `COMPLETED / INDEPENDENT REVIEW PASSED / MERGED` | 已增加 scenario-specific Q availability，完成 EF/A0/A1 最小适配并重新建立 M0/M1/M2 correctness；PR #16 已人工合并。原 R3/R4 evidence 仅对应修订前模型。 |
| R5 | Pilot & Mechanism Diagnosis | `COMPLETED / INDEPENDENT REVIEW PASSED / MERGED` | 已执行冻结的 3 models × 3 budgets Pilot、EF/A0/A1 correctness 与机制诊断；Pilot 结果没有被用于反向调参。 |
| R6 | Formal Data Preparation + Experiment Matrix Freeze | `R6-A REVIEWED / R6-B IN PROGRESS / DRAFT PR #18` | R6-A 已冻结 Gulf Coast Formal-ready data；R6-B 只冻结 E1–E5、LOHO、synthetic OOS、Memory ablation、seeds、统计与身份规则。Formal scientific runs=0；不得进入 R7。 |
| R7 | Formal Experiments | `NOT_STARTED / NOT_AUTHORIZED` | 按冻结设计执行正式实验，保存完整 source/config/status/raw evidence 与失败结果。 |
| R8 | Results & Paper Evidence | `NOT_STARTED / NOT_AUTHORIZED` | 汇总 scientific、correctness 与 algorithm 三条证据链，形成可审计结果和论文证据；novelty wording 仍须专门治理。 |

A1 已在 R4 冻结、实现和验证；R6-B 不修改其 Memory/Candidate/Full Exact Certification 结构。R6-B 的正式矩阵权威为 [R6_FORMAL_EXPERIMENT_MATRIX_v1.md](R6_FORMAL_EXPERIMENT_MATRIX_v1.md) 及其机器配置；在独立复审和人工合并前不得启动 R7。Pilot baseline 不自动升级为正式设计。

## 2.1 当前 Q-F-R availability/model revision

本次用户批准的科学修订见 [QFR_AVAILABILITY_RESEARCH_REVISION_v2_1.md](QFR_AVAILABILITY_RESEARCH_REVISION_v2_1.md) 和 [QFR_AVAILABILITY_MODEL_SPEC_v2_1.md](QFR_AVAILABILITY_MODEL_SPEC_v2_1.md)。原 R0–R4 frozen documents、实现提交和 evidence 保留为修订前 provenance，不回写其科学定义。

当前 revision 仅允许：同步修订规格；最小修改共享 Q-F-R schema/model/accounting/recourse；必要适配 EF/A0/A1；依据 [QFR_AVAILABILITY_CORRECTNESS_PROTOCOL_v2_1.md](QFR_AVAILABILITY_CORRECTNESS_PROTOCOL_v2_1.md) 重新验证 M0/M1/M2 的 `EF ≈ A0 ≈ A1`；创建一个 Draft PR 并停在独立复审门。

明确禁止在本 revision 中运行 pilot、OOS、正式实验、性能实验，或修改 Memory、Candidate ranking、exact certification、convergence、fixed-budget accounting 和 objective。

## 3. Historical R2 implementation boundary

以下记录保留 R2 当时的实施边界；R2 现已完成并合并：

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

当前 roadmap 更新同步已完成的 availability/model revision 与已明确授权的 R5 Pilot。它不把修订前 correctness evidence 解释为修订后证明，也不授权 R6、OOS 或正式实验。
