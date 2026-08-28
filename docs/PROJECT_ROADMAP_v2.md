# PROJECT ROADMAP v2 — R0 and redesign gates

状态：新 Q-F-R 路线阶段规划。R0 仅新增设计文档；本表不构成 R1–R8 的自动启动授权。

## 1. 当前阶段与设计权威

R0 将用户确认的异质物资 Q-F-R 两阶段鲁棒设计落入仓库。当前数学规范为 [MODEL_SPEC_v2.md](MODEL_SPEC_v2.md)，研究问题和证据链为 [RESEARCH_DESIGN_v2.md](RESEARCH_DESIGN_v2.md)，算法方向为 [ALGORITHM_DIRECTION_v2.md](ALGORITHM_DIRECTION_v2.md)。历史与本次静态核验见 [REDESIGN_TRACEABILITY_v2.md](REDESIGN_TRACEABILITY_v2.md)。

v1 和 N0–N6 仍是 old-route historical design/evidence；PR #9 为未合并的旧路线诊断历史；它们不再给新科学路线提供阶段完成或算法正确性授权。PR #10 只提供已复审的通用工程 hardening。

R0 的 Draft PR 完成后立即停止，等待独立复审和人工合并。即使 CI 成功，也不等于新模型已实现、已正确或允许开始 R1。

## 2. R1–R8 工作路由

以下是依赖顺序和职责规划，不是本轮实施清单；每个阶段仍需用户明确启动与验收。具体实施任务在阶段启动时细化，不得暗中改变 R0 科学定义。

| 阶段 | 后续工作范围 | 进入下一环节所需证据 |
| --- | --- | --- |
| R0 | 新研究设计、数学规格、算法方向、追溯及路线图 | 独立复审、人工批准并合并；本轮只做到 Draft PR |
| R1 | 新数据定义与 M0 — Q 基线 | 定义域、会计、开发微型实例正确性；不借用旧同名模型证据 |
| R2 | M1 — Q+F | 能力预留/行使及 F=0 时 M1=M0 的新自动化证据 |
| R3 | M2 — Q+F+R | F 专属保障、单预算及仅保留 r=0 时 M2=M1 的新自动化证据 |
| R4 | EF 与 A0 Standard C&CG | 新模型 EF≈A0；规格与验收标准先冻结再使用 |
| R5 | A1_new 设计、复审、实现与正确性 | 先冻结最终改进机制，再实现并验证 EF≈A0≈A1_new |
| R6 | 小规模预注册 pilot、执行能力与科学信息量诊断 | 保留不良/失败结果，评估 runtime、规模和识别风险，不产生正式结论 |
| R7 | 正式科学实验设计冻结与 literature positioning | 基于 pilot 容量确定正式参数、OOS/规模/统计方案及可支持的创新措辞 |
| R8 | 经授权执行正式实验 | 分离报告三条证据链；结果、失败、audit/replay 可追溯 |

R0 未选择 A1_new 机制，也未规定 R6/R7 的数值。旧阶段号 N4/N5/N6/N7 的协议不会自动成为这些 R 阶段的协议。

## 3. 冻结时序

1. 新数据/模型测试使用参数前：登记 development fixtures，遵守生产定义域；不作为正式科学参数。
2. 新 EF/A0 正确性比较前：冻结新路线验收协议、容差、gap/violation、精确状态接受规则、初始场景及并列解处理。R0 不确定这些数值。
3. A1_new 实现前：完成最终机制设计复审、算法协议冻结；不得默认沿用旧 Memory/Candidate 架构。
4. Pilot 科学运行前：登记 pilot 参数、seed、规模、限制、停止规则、计时与 audit；先固定 source/protocol/config 再观察结果。
5. Pilot 后、正式运行前：冻结正式预算网格、参数标定、scenario generation、train/test sizes、seed registry、规模档和 timing/OOS repetitions、失败统计与推断方案。

后一步不能重定义前一步已经使用的正确性标准来让结果通过。Development/pilot 参数不得因为表现好而自动升级为 formal；不得利用旧 N7-pre 的失败或新结果进行“调到机制激活”的循环。若确需重新打开科学设计，应停止并经显式治理决策，不得边改边跑。

## 4. 实验与规模的必守原则

三条证据链分别是 model correctness、scientific/managerial findings、algorithm performance。M0→M1→M2 比较用于机制增量价值；B、h、a、需求风险、δ、F/R 成本及 η 的分析围绕统一 Q-F-R 模型。

正式主实验必须有多种异质物资并体现三类代表性特征；不继承旧 |I|=1 正式范围。Small 用于 EF/A0/A1_new correctness，medium 用于主要性能比较，large 用于 scalability/stress，EF 不可执行时可仅 A0/A1_new。各档物资数和场景数均未冻结。

Independent OOS 固定第一阶段，仅让 x、u 对新场景响应；评估缺货、recourse/total cost、预算可行性、F fulfillment 和 worst/tail performance。测试集不用于重新选择第一阶段或挑参数。Train/test sizes、seed 数、重复次数须在 pilot 后确定。

R0 不设正式统计阈值、最后创新措辞或论文标题。Literature-positioning review 必须在正式主张形成前完成，不能将标准 C&CG 宣称为创新。

## 5. PR、证据与停止规则

- 每个主要阶段原则上一个 Draft PR；阶段内修复回到同一个 PR，不按模块、seed 或单次 run 拆 PR。
- 完成阶段后停止复审；不自动 merge，不自动进入下一阶段。
- 代码、配置、协议、commit/tree、环境、状态与原始输出必须可追溯；复用通用工程工具也不能复用旧科学结果充当新证据。
- 保存失败、首次异常与非激活结果；不覆盖、删除、换 seed、事后调容差或悄悄扩大范围。
- 科学参数/算法结构的变更须显式说明原因并重新验证；旧证据只覆盖其原 source 和定义。
- 若发现模型矛盾、正确性错误或 evidence-integrity 问题，停止相关执行并请求复审，不以工程通过代替科学通过。

本轮只允许 branch `r0/qfr-research-redesign` 上的一个 R0 Draft PR，内容仅为本套 v2 文档。模型、算法、实验代码及旧 evidence 不修改；scientific runs=0，solver runs=0。
