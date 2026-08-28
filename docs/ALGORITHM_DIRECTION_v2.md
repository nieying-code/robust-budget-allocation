# ALGORITHM DIRECTION v2 — New Q-F-R route

状态：R0 仅冻结算法研究方向，不冻结最终改进机制，不包含算法实现。

## 1. 适用模型与证据边界

算法必须针对 [MODEL_SPEC_v2.md](MODEL_SPEC_v2.md) 的两阶段有限场景 Q-F-R 模型重新构建。共同目标是：

$
\min_{Q,F,z}\left[C_Q+C_F+C_R+\max_{\omega\in\Omega}\mathcal V_\omega(Q,F,z)\right],
$

其中 $\mathcal V_\omega$ 是给定灾前决策、同一预算 B 下最小化实际采购/生产支出与缺货损失的 recourse 值。场景 recourse 保留需求满足、受保障柔性能力上限及 C^pre+C_ω^E≤B；不得把缺货罚金放入现金预算，也不得把 F 的预留量当成实际采购量 x。

旧 N6 的 EF≈A0≈A1 只证明旧模型的正确性，不能作为新模型的 correctness evidence。现有工程框架、求解状态认证、source/hash/replay 工具可在后续审计适配，但旧科学模型、oracle 公式、场景生成及算法状态机不会因为代码已存在而成为新路线定义。

## 2. 冻结的研究顺序

| 组件 | 研究角色 | R0 冻结边界 |
| --- | --- | --- |
| EF | small-scale correctness benchmark | 全场景表示新模型，作小规模基准；不实现 |
| A0 — Standard C&CG | 标准算法 baseline | 按新模型建立 master、recourse 和完整最坏场景验证；不实现 |
| A1 — Improved C&CG | 待研究的改进算法 | 方向保留，最终改进机制不冻结、不实现 |

顺序：EF → A0 → A1；正确性证据先建立 EF≈A0，再建立 EF≈A0≈A1_new。Standard C&CG 本身不是论文算法创新，模型新符号或旧算法改名也不是创新证明。

## 3. 正确性和认证责任

未来 EF、A0、A1_new 必须使用同一新模型实例、场景集、第一阶段可行域、recourse 和目标口径；模型消融也遵守新 nesting：M1|F=0=M0、M2|R={0}=M1。

有限场景下，给定第一阶段的正式上界须由对完整 Ω 的最坏 recourse 值的有效精确认证支持；有效 master 的界与该上界共同支持收敛判断。只检查部分场景不足以认证全场景最坏值。错误、超时、未知状态或不完整求解不能伪称 exact optimal。

这些是与数学问题一致的证据责任，不是把旧 Phase I/II/III 协议移植到新模型，也不提前选择 A1 的搜索、记忆或触发规则。

在新路线正确性验收首次使用前，必须登记并冻结：目标一致性绝对/相对容差、gap/violation 标准、solver optimality 接受规则、初始场景、并列场景/多解处理与 replay 字段。R0 不设置新数值，也不宣称旧科学协议自动适用。既有通用 solver policy 不在 R0 修改。

比较不能只看最终目标；后续须检查可重算会计、recourse、有效上下界与终止证书。多解应按预登记规则比较，不能为获得一致外观事后改变模型或容差。

## 4. A1 尚未冻结

旧路线的 Memory-Guided Three-Phase C&CG，以及 Memory Inspection、Candidate Search、Phase I/II/III、旧 scoring、memory eligibility/lifecycle 和状态机均不自动继承。

R0 不决定使用、删除或替换 Memory，不指定 candidate ranking、触发条件、公式、伪代码或新的 A1_final。旧 N7-pre 的诊断只解释科学路线转向，不能直接替新模型选择算法结构。

后续在实现 A1_new 前，须有独立的算法设计依据、明确规格和复审；实现后重新完成 EF≈A0≈A1_new。若之后改变最终算法结构，需要新验证，不能借用旧路线或旧版本证据。不得用 pilot 反复挑选表现最好的算法再事后描述成预先固定方案。

## 5. 计算评价边界

- small：建立新模型 EF/A0/A1_new 正确性证据。
- medium：主要 A0/A1_new 性能比较。
- large：可扩展性与压力测试；EF 若不可执行，可仅比较 A0/A1_new，但须记录限制，不虚构 EF 正确性证书。

性能证据按 |I|、|Ω| 和问题规模分析 runtime、iterations、oracle workload 和 convergence behavior。A0/A1_new 必须有一致的计时边界、环境、solver policy 和可追溯输入；preflight、数据构建、算法时间、序列化/audit 应分开报告。R0 不新增 solver 设置，不运行 solver。

具体规模档、seed 数和 timing repetitions 在后续 pilot 后决定，不能现在照抄旧单物资矩阵。正式科学实例必须体现异质多物资。A1_new 不保证更快，失败和不占优必须如实保留。

## 6. OOS 不是算法认证替代品

OOS 固定训练得到的 Q*、分等级 F* 和等级选择 R*，仅允许 unseen scenario 的 x、u 重新响应；继续受同一固定总预算约束。它支持科学/管理证据链的缺货、成本、预算、兑现和尾部表现分析，不替代 EF≈C&CG 或收敛证书。

R0 只冻结上述方向。没有模型/算法代码变更，没有 solver run，没有新的实验或正确性结果。
