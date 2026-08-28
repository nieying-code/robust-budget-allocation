# REDESIGN TRACEABILITY v2 — Historical boundary and R0 audit

状态：R0 设计追溯；不改写旧路线，不生成科学结果。日期：2026-08-28。

## 1. 经核验的工程起点

| 对象 | 锚点 / 状态 |
| --- | --- |
| R0 base / remote main commit | `c15986c865aa374201ac07ddf38a0e3a74139cb0` |
| R0 base / main tree | `07503361df2039d02be5324ecc2d2604c6611a5e` |
| [PR #10](https://github.com/nieying-code/robust-budget-allocation/pull/10) reviewed final head | `61551865b67ba87b2144ae222019ded484d5e6dc` |
| PR #10 merge commit | `c15986c865aa374201ac07ddf38a0e3a74139cb0` |
| PR #10 merge time / state | `2026-08-28T14:13:04Z` / MERGED |
| [PR #9](https://github.com/nieying-code/robust-budget-allocation/pull/9) head | `cb04cdb0254bfb07e6faaa3281f814c3ee169345` |
| PR #9 state | CLOSED WITHOUT MERGE；mergedAt 为空 |
| PR #9 branch | `n7-pre/option-memory-confirmation`，保留 |
| R0 branch | `r0/qfr-research-redesign`，从上述已验证 clean main 创建 |

Fetch 后核验 main commit/tree 与人工指定值一致；PR #10 reviewed head 已在 main 历史中，main tree 与 reviewed head tree 相同。PR #9 相对旧 main 的六个提交均非当前 main 的祖先；main 文件树未包含 N7-pre 专用科学模块、配置或证据文件。R0 开始前工作树 clean。

R0 最终 commit/tree 与 PR URL 由 Git/PR 作为文档集合的外部锚点报告，不把文档自己的 commit SHA 嵌入自身制造循环。基线、旧科学证据及 v1 文件均不因本次文档冻结而重写。

## 2. 旧路线的保留关系

旧科学路线历史：

N0 → N1 → N2 → N3 → N4 → N5 → N6 → N7-pre。

旧 Q-R-F / F-OPTION 路线以 Quantity、常规供应保障和二元应急采购权为核心；N6 与 N7-pre 属于该路线，不是新模型的实验。N7-pre 的诊断结果为：

`N7_PRE_OPTION_GATE_FAILED`

该结果触发正式 scientific redesign，而不是继续降低费用、替换 seed 或追加试验以强迫旧 Option 激活。PR #9 已关闭但未合并，其 branch、commits、讨论及诊断证据保留为 historical scientific provenance，不再是待并入 main 的候选路线。

[PR #9 closing provenance comment](https://github.com/nieying-code/robust-budget-allocation/pull/9#issuecomment-5453594299) 保留了此决定。R0 不删除旧结果，也不宣布旧科学结果错误或无效；诊断在其预注册问题和样本范围内有历史意义，不能外推为新 Q-F-R 机制的结果。

## 3. 通用工程增强与科学设计分离

Transition delta audit 的结论为 `GENERIC_FIXES_EXIST_AND_ARE_SEPARABLE`。可分离增强通过 PR #10 从 clean main 重新实现、独立复审并人工合并，而非 merge/cherry-pick PR #9：

- 原始 JUnit XML、实际 testcase 状态与保存计数的一致性检查。
- 按方法要求完整 engine audit，并将内外 source manifest 做 canonical 全内容绑定。
- Gzip evidence 写入复用已有 bounded atomic replace retry。
- 真实浅克隆与 production source-entry 的防回归覆盖。

PR #10 是通用工程 hardening，不是 PR #9 科学路线的替代实现，也不表示 N7-pre scientific logic 已进入 main。Egg-info source-boundary 修复没有迁移，因为 main 原有 package 扫描范围已经正确。

保留人工独立复审的非阻断历史备注：PR #10 首次完整 Linux regression 中，一个未修改的旧 heartbeat 测试因实际冲突 7 次而断言要求 8 次失败；随后单测及完整 regression 通过，最终为 726 passed、4 skipped、100 deselected。复审将其判为 existing test stability issue / non-blocking note。这是历史 provenance，不是 R0 新运行的测试，不因本任务修改该测试。

## 4. 新旧科学含义映射

| 维度 | v1 / old route（保留历史） | v2 / current redesign |
| --- | --- | --- |
| 研究顺序 | old Q-R-F / F-OPTION | heterogeneous-material Q-F-R |
| Q | 旧常规采购与旧供应商履约结构 | 灾前实体储备，灾时有效量 a_i Q_i |
| F | 二元 y_F、固定 K_F 的应急采购权 | 连续分等级 F_ir 的灾前柔性能力预留 |
| R | 常规供应商合同保障 | 仅保护 F 兑现，按能力收费，无固定保障费 |
| 物资范围 | 旧单物资正式范围 | 新正式科学主实验覆盖异质多物资 |
| h | 旧场景未使用资源符号 | 新 h_i 是储存/保鲜成本参数 |
| 时间 | 旧两阶段 | 仍为两阶段，Q-F-R 不是三阶段 |
| 新 M0/M1/M2 | 不继承旧同名模型语义 | Q / Q+F / Q+F+R |
| 算法 | 旧 Memory-Guided Three-Phase C&CG | EF→A0→A1_new；最终改进机制未冻结 |
| 正确性 | 旧 EF≈A0≈A1 证据 | 必须重新建立新模型 EF≈A0≈A1_new |

同名符号和模型编号不是可兼容接口声明。旧参数、seed、场景公式、库存结构、Option Gate、Memory 诊断和旧算法机制均未迁入 v2 科学定义。

## 5. 文档权威与冻结内容索引

| 文件 | 新路线职责 |
| --- | --- |
| [RESEARCH_DESIGN_v2.md](RESEARCH_DESIGN_v2.md) | 问题、异质性、机制链、证据链、OOS/规模及创新边界 |
| [MODEL_SPEC_v2.md](MODEL_SPEC_v2.md) | 变量/参数域、线性 F-R、需求与兑现、单预算、目标和 nesting |
| [ALGORITHM_DIRECTION_v2.md](ALGORITHM_DIRECTION_v2.md) | EF/A0/A1_new 方向及不自动继承旧算法的边界 |
| [PROJECT_ROADMAP_v2.md](PROJECT_ROADMAP_v2.md) | R1–R8 依赖规划、事前冻结、独立复审和停止门槛 |
| 本文件 | 基线、旧证据保留、工程/科学分离及 R0 静态审查 |

v1 文件完整保留，不覆盖、不删除。不把 v1 的单物资、旧 Option、旧实验矩阵或算法协议作为 v2 的隐含约束。本套文件是新路线当前设计；R0 PR 仍需独立复审和人工合并，后续阶段仍需单独授权。

## 6. R0 静态一致性自审

以下是文档和 Git 变更边界的检查，不是 solver 或新模型 correctness test。

| # | 检查项 | 结论 / 定位 |
| --- | --- | --- |
| 1 | 固定预算只有一个 B | PASS；MODEL §7：每场景 C_Q+C_F+C_R+C_ω^E≤B |
| 2 | 缺货损失不进入现金预算 | PASS；MODEL §6–8 将 L_ω^S 仅计入目标 |
| 3 | F 始终是灾前 capacity reservation | PASS；MODEL §3–4，与实际 x 分开 |
| 4 | x 始终是灾后 actual exercise | PASS；MODEL §5–6，阶段揭示后响应 |
| 5 | R 仅保护 F fulfillment | PASS；MODEL §5 的 ρ 仅乘 F_ir |
| 6 | 不携带旧 y_F/K_F/Option 机制 | PASS；仅在历史对照和排除说明中出现，没有进入新方程 |
| 7 | 未改成三阶段优化 | PASS；两阶段，Q-F-R 是机制链 |
| 8 | 三模型 nesting 一致 | PASS；F=0 时 M1=M0，仅保留 r=0 时 M2=M1 |
| 9 | 未断言现实需求与中断独立 | PASS；只声明 baseline 不显式建模相关结构 |
| 10 | 未加入 DRO/Γ uncertainty | PASS；这些结构仅作为排除项提及 |
| 11 | 未自动继承旧 Memory A1 | PASS；A1_new 机制明确尚未冻结 |
| 12 | 未提前冻结实验数值 | PASS；仅固定用户要求的模型等级及数学定义域，不指定网格/seed/规模 |
| 13 | 未宣称 novelty 已证明 | PASS；最终措辞 NOT FROZEN AT R0，待文献定位复审 |
| 14 | v1 历史文件完整保留 | PASS；R0 diff 仅新增本套五份 v2 文档 |
| 15 | scientific code modifications=0 | PASS；模型、算法、实验代码、配置及旧 evidence 不修改 |

补充方程检查：η 与 c^R 的基础值及严格顺序一致；等级最多选一个；F 不设一般需求上限；需求满足使用 ≥；p_i^F 无场景索引；预留/行使现金分别计费；a 导致的数量损失不另收独立损耗罚金；相对完全 recourse 的文档论证不被包装成计算证据。

## 7. 未冻结事项与本轮停止点

正式 budget levels、数值标定、seed values/counts、scenario counts、train/test sizes、规模阈值、timing/OOS repetitions、最终 A1 机制及 ranking/memory、统计显著性阈值、novelty wording 和论文标题都未冻结。它们是后续阶段任务，不是 R0 缺陷，也不能由本次编辑默认填充。

本轮 scientific code changes=0、scientific runs=0、solver runs=0；不生成科学输出、不修改 PR #9 历史。提交并创建唯一 R0 Draft PR 后停止，不合并、不开始 R1，等待独立复审。
