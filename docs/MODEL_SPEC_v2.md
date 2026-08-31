# MODEL SPEC v2 — Heterogeneous-material Q-F-R

状态：R0 冻结数学设计稿；Q availability 修订见 `QFR_AVAILABILITY_MODEL_SPEC_v2_1.md`。本文件中的可用 Q 表达已作一致性勘误，不改变已实现模型。v1 数学规范保留为历史，不是本规范的隐含补充。

## 1. 时间、集合与符号

- I：非空有限物资集合；正式科学主实验包含普通、保鲜型、易腐型代表性物资；R0 不固定 |I|。
- Ω：非空有限场景集合；R0 不固定 |Ω| 或场景生成数值方案。
- $\mathcal R=\{0,1,2\}$：每个物资单个代表性柔性通道可选可靠性等级；r=0 为基础等级。
- Stage 1：灾前 Q_i、F_ir、z_ir；Stage 2：需求和中断揭示后 x_iω、u_iω。

Q-F-R 是提前实体化、延迟实体化及其保障的机制链，不是三阶段优化。不存在灾后重选 Q/F/R。R 是机制名称，$\mathcal R$ 是等级集合，不另设连续“保障资源”变量。

符号隔离：本规范 h_i 是储存/保鲜成本参数，不是旧 v1 的未使用资源变量；x_iω 是灾后柔性采购/生产量。不得根据旧同名变量推断新含义。

## 2. 参数、基本域和单位

所有数值均有限。以下是定义域，不是正式参数标定。

| 参数 | 含义 / 单位 | 定义域 |
| --- | --- | --- |
| B | 全周期总预算 / 货币 | B≥0 |
| τ | 外生规划、等待期 / 时间 | τ≥0 |
| c_i^Q | 单位实体采购支出 / 货币每物资单位 | >0 |
| h_i | 单位时间储存、保鲜负担 / 货币每物资单位每时间 | ≥0 |
| a_i | 灾时有效留存比例 / 无量纲 | 0<a_i≤1 |
| $\bar F_i$ | 名义可预留能力上限 / 物资单位 | ≥0，有限且有实际能力含义 |
| c_i^F | 单位预留能力费用 / 货币每能力单位 | >0 |
| c_ir^R | 单位预留能力可靠性 premium / 货币每能力单位 | c_i0^R=0<c_i1^R<c_i2^R |
| η_ir | 中断损失缓解比例 / 无量纲 | η_i0=0<η_i1<η_i2<1 |
| d_iω | 灾后需求 / 物资单位 | ≥0 |
| $\rho^Q_{i\omega}$ | 场景下预置库存可用率 / 无量纲 | $0\le\rho^Q_{i\omega}\le1$ |
| δ_iω | 基础柔性能力损失比例 / 无量纲 | 0≤δ_iω≤1 |
| p_i^F | 单位实际柔性采购/生产支出 / 货币每物资单位 | >0，基线不随 ω 变化 |
| s_i | 单位缺货经济/社会损失 / 货币每物资单位 | >0 |

F 的能力单位指单次灾后响应期能够交付的物资数量；若现实数据以产能速率表示，应在未来数据标定中转换到统一响应期数量。本规范不新增时间阶段。

不额外规定 p_i^F 与 c_i^Q、s_i 的大小关系，不预设机制一定有价值。h_i、a_i 分别表达储存支出与有效数量，不强加函数关系。τ 外生；不建 a_i(τ) 动态衰变方程。

## 3. 第一阶段线性表示

$
Q_i\ge0,\quad F_{ir}\ge0,\quad z_{ir}\in\{0,1\}.
$

$
\sum_{r\in\mathcal R}z_{ir}\le1,\qquad
0\le F_{ir}\le\bar F_i z_{ir}\quad\forall i,r,
\qquad F_i=\sum_r F_{ir}.
$

每个物资/通道最多选一个等级，可完全不预留。F_i 是派生总能力，F_ir 将能力与等级分开以避免 F×等级的双线性乘积。$\bar F_i$ 是物理/合同能力边界，不是任意 Big-M。不要求 F_i≤max_ω d_iω：超额名义预留可以补偿兑现损失。

当 F_ir=0 时，相应 z_ir 可有不影响经济结果的冗余标记；不加入最小预留量、固定费或“零能力必须零标签”的新机制。R 的经济配置应结合实际正能力及其 premium 解读，不能仅凭 z 标签认定保障有价值。

## 4. 灾前成本与有效实体储备

$
\begin{aligned}
C_Q(Q)&=\sum_i(c_i^Q+h_i\tau)Q_i,\\
C_F(F)&=\sum_{i,r}c_i^F F_{ir},\\
C_R(F)&=\sum_{i,r}c_{ir}^R F_{ir},\\
C^{pre}&=C_Q+C_F+C_R,\qquad Q_{i\omega}^{available}=a_i\rho^Q_{i\omega}Q_i.
\end{aligned}
$

Reliability 只有随能力计收的 premium，没有固定 Reliability fee。普通物资用低 h、高 a 表示；保鲜型用高 h、相对高 a 表示；易腐型用低/中 h、较低 a 表示。三者共用方程，没有另建三套模型。

不另加 $w_i(1-a_i)Q_i$ 独立损耗成本；也无轮换、补货、库龄、动态变质、多期库存、残值、处置成本或剩余物资罚金。

## 5. 场景揭示与柔性能力兑现

$
\mathcal U=\{(d_\omega,\rho^Q_\omega,\delta_\omega):\omega\in\Omega\},\qquad
\rho_{i\omega}^r=1-(1-\eta_{ir})\delta_{i\omega}.
$

$
x_{i\omega}\ge0,\qquad
x_{i\omega}\le\sum_{r\in\mathcal R}\rho_{i\omega}^r F_{ir}
\quad\forall i,\omega.
$

ρ 是由场景和等级参数得到的常数，约束线性。R 只缓解 δ 对 F 的兑现损失，不影响实体 Q、需求、场景概率或预算。

边界含义：

- δ_iω=0 ⇒ ρ_iω^r=1：R 不创造名义能力以外的供应。
- δ_iω=1 ⇒ ρ_iω^r=η_ir：基础等级可完全中断，最高等级仍非绝对安全。
- F_i=0 ⇒ x_iω=0、该物资 C_R=0：R 没有独立于 F 的经济价值。
- 因 0≤ρ≤1，实际使用量不超过被预留的名义能力。

Baseline does not explicitly model demand–supply-disruption correlation, so that demand-risk and supply-disruption effects can be separately identified. 这不等于宣称现实独立，也不在本阶段指定随机独立抽样规则。

本基线不含 Γ_D/Γ_S、budgeted uncertainty、Wasserstein/moment ambiguity、DRO、概率加权随机规划、共同潜在灾害变量、copula、相关参数或联合分布估计。

## 6. 需求满足和场景成本

$
u_{i\omega}\ge0,\qquad
a_i\rho^Q_{i\omega}Q_i+x_{i\omega}+u_{i\omega}\ge d_{i\omega}
\quad\forall i,\omega.
$

需求满足是不等式：允许实体储备超过需求，不强制额外采购，也不加入新的 leftover 变量或惩罚。各物资分别满足需求；没有跨物资替代或能力转移。

$
C_\omega^E=\sum_i p_i^F x_{i\omega},\qquad
L_\omega^S=\sum_i s_i u_{i\omega}.
$

x 是灾后真实采购/生产，不是预留能力 F；s_i u_iω 是经济/社会损失，不是现金。非最坏场景的 epigraph 表示可能存在多个等价第二阶段解；未来结果提取须说明所报告解是否为给定第一阶段下的最优 recourse，不能据冗余 slack 作管理解释。R0 不冻结 tie-break 或新的数值容差。

## 7. 同一全周期固定预算

$
C_Q+C_F+C_R+C_\omega^E\le B\quad\forall\omega\in\Omega.
$

该式对每个可能实现的场景成立，不把不同互斥场景的现金支出相加。灾前支出在场景揭示前固定。没有第二个灾后预算、外部资金或只约束灾前的替代预算。

$
\text{unused cash}_\omega=B-C^{pre}-C_\omega^E\ge0.
$

允许 unused cash>0；不强迫全额支出。缺货损失不进入此式。Reservation 支付 capacity availability 的成本；exercise 支付实际交付数量的成本，二者不是双重计费。

## 8. 完整 M2 目标与两阶段形式

有限场景完整表示：

$
\begin{aligned}
\min_{Q,F,z,x,u,\theta}\quad &C_Q+C_F+C_R+\theta\\
\text{s.t.}\quad &\text{第 3、5、6、7 节约束},\\
&\theta\ge C_\omega^E+L_\omega^S\quad\forall\omega.
\end{aligned}
$

每种成本在目标中只计一次。实际行使支出同时属于目标和现金预算不是重复计费，而是成本评价和可行性约束的不同作用。

令 $\mathcal X(Q,F,z;\omega)$ 为第 5–7 节给定第一阶段的 recourse 可行域，等价两阶段形式为：

$
\min_{(Q,F,z)\in\mathcal Y}
\left\{C^{pre}+\max_{\omega\in\Omega}
\min_{(x_\omega,u_\omega)\in\mathcal X(Q,F,z;\omega)}
\sum_i(p_i^Fx_{i\omega}+s_iu_{i\omega})\right\}.
$

$\mathcal Y$ 包含第 3 节第一阶段约束和必要条件 C^pre≤B；后者已由每场景预算及 C_ω^E≥0 蕴含，不是额外预算。因为场景 recourse 之间没有共享的灾后决策，epigraph 完整表示与上述 min–max–min 的最优值一致。

静态可行性检查：对任意 $\mathcal Y$ 中的第一阶段，选 x_iω=0、u_iω=max{d_iω−a_iQ_i,0} 即可满足需求及预算，故允许缺货的设计提供相对完全 recourse。全零预置/预留也可行。正采购/预留成本、有限 B 和容量界限阻止第一阶段无成本无限扩张。这是方程层面的检查，不是程序正确性或实验结果。

## 9. M0/M1/M2 的精确定义

### M0 — Q

只决定 Q≥0，F 关闭，R 不存在，x_iω=0。保留灾后缺货 u≥0、$a_i\rho^Q_{i\omega}Q_i+u_{i\omega}\ge d_{i\omega}$，预算 C_Q≤B，目标 min C_Q+θ，θ≥Σ_i s_i u_iω。

### M1 — Q+F

仅允许 r=0，η_i0=0、c_i0^R=0，故 C_R=0；使用与完整模型相同的基础等级能力表示。灾后约束为：

$
x_{i\omega}\le(1-\delta_{i\omega})F_i.
$

预算 C_Q+C_F+C_ω^E≤B；目标 min C_Q+C_F+θ，θ≥C_ω^E+L_ω^S。无付费 R 决策。

### M2 — Q+F+R

允许全部 r∈{0,1,2}，采用第 3–8 节完整模型。三个模型共用同一实例、Ω、d、基础 δ、a、价格、容量、预算和目标会计。

$
\boxed{M1\big|_{F=0}=M0},\qquad
\boxed{M2\big|_{\mathcal R=\{0\}}=M1}.
$

第一条中 capacity 约束强制 x=0、C_F=0；去掉无经济作用的等级标签便得到 M0。第二条中 C_R=0、ρ=1−δ，全部预算、recourse 和目标约束成为 M1。退化关系是经济决策投影与最优值的等价，不要求不同最优解时任意 solver 返回相同标签。未来必须用新模型自动化退化测试验证；R0 不写测试或实现。

## 10. 后续实现契约与禁止继承

未来 schema 必须验证全部严格正数、比例界限、等级严格顺序、完整 item/level/scenario keys、有限数值及确定性的场景身份。Development fixtures 不得放宽生产定义域。任何数值容差、初始场景或并列解报告规则必须在使用前单独登记，不由 R0 发明。

后续必须独立核算 C_Q、C_F、C_R、C_ω^E、L_ω^S、unused cash、有效 Q 和可兑现 F，并验证需求、能力、预算与目标闭合。旧代码中同名 M0/M1/M2、旧单物资限制、供应商级保障、二元 Option 费用、旧库存/未使用资源等结构均不得自动套用。仅通用工程能力可以在后续经审计复用。

本规范不包含模型 builder、EF/oracle/C&CG 实现、scenario generator、正式数值标定或新正确性证据。
