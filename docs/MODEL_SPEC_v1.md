# MODEL SPEC v1

状态：N0 最终数学规范；结构冻结，数值参数推迟到 N7 前冻结。

## 1. 集合

- i∈I：资源；j∈J：供应商。
- k∈K_j：供应商 j 的有限 Reliability 等级；k=0 为基础等级，K_j 具有冻结的弱序。
- ω∈Ω：有限场景。三模型使用同一 Ω。

首版为单期、非易腐、两阶段、无供应恢复。

数学规范和代码接口保留一般有限集合 I；但本项目首版研究、E2–E6 正式科学实例和论文核心主张固定 |I|=1。多物资实例不进入正式规模矩阵，只作为未来扩展。

## 2. 参数

- B：唯一固定全周期现金预算。
- c^Q_ij：常规采购基础单价；U_ij：供应商—资源采购上限。
- a_jk≥0：供应商级 Reliability 固定保障费；π_ijk≥0：等级相关单位 premium。基础等级 a_j0=π_ij0=0。
- d_iω≥0：需求；ρ_ijkω∈[0,1]：等级 k 下的场景履约率。
- K_F>0：标准 Option fee；F_bar>0：合同允许的最大场景应急采购金额。
- p^F_iω>0：场景应急采购价格；s_i>0：单位缺货经济损失。

若 k' 高于 k，则 a_jk'≥a_jk、π_ijk'≥π_ijk，且对每个 i,ω 有 ρ_ijk'ω≥ρ_ijkω。具体 K_j 大小、费用和履约改善数值不在 N0 冻结。

## 3. Stage 1 变量

- z_jk∈{0,1}：供应商 j 选择 Reliability 等级 k；Σ_k z_jk=1。
- q_ijk≥0：在供应商 j 所选等级 k 下签约的资源 i 数量；q_ijk≤U_ij z_jk。
- y_F∈{0,1}：是否购买标准 F-OPTION，仅 M2 可自由选择。
- θ≥0：最坏场景补救经济损失的上界。

按等级拆分 q 避免 ρ·q·z 双线性。未使用供应商可选择基础等级而不产生 Reliability premium。

## 4. 成本分解与防重复计费

    C_Q(q)=Σ_i,j,k c^Q_ij q_ijk,
    C_R(q,z)=Σ_j,k a_jk z_jk + Σ_i,j,k π_ijk q_ijk,
    C_F(y_F)=K_F y_F.

C_Q 只计基础资源价格；C_R 只计高于基础等级的固定保障费和单位 premium；C_F 只计购买 Option 的固定费用。任何输入价格不得同时进入两个分量。基础等级 Reliability 增量成本为零。

## 5. 场景数据与常规到货

场景 ω 至少包含 d_iω、所有等级下的 ρ_ijkω 和 p^F_iω。常规实际到货为：

    regular_delivered_iω = Σ_j,k ρ_ijkω q_ijk.

Reliability 只通过 ρ 影响常规到货，不修改需求、预算、应急价格或缺货 penalty。

## 6. Stage 2 变量与物理平衡

- g_iω≥0：M2 场景应急采购量；M0/M1 固定为 0。
- served_iω≥0：满足需求的量。
- u_iω≥0：缺货/未服务量。
- h_iω≥0：已到货但未使用资源。
- E_ω≥0：真实应急采购支出。

每个 i,ω：

    served_iω + u_iω = d_iω,
    served_iω + h_iω = regular_delivered_iω + g_iω.

并且：

    E_ω = Σ_i p^F_iω g_iω,
    E_ω ≤ F_bar y_F.

因此 y_F=0 强制 E_ω=0；因 p^F_iω>0，进而 g_iω=0。没有基础应急采购变量。h 不计持有、处置、过期成本或残值，但必须报告。

## 7. 唯一预算

Stage 1 必须满足：

    C_Q + C_R + K_F y_F ≤ B.

每个场景还必须满足：

    C_Q + C_R + K_F y_F + E_ω ≤ B.

F_bar 是合同上限而非额外资金；实际 E_ω 同时受合同上限和 B 的剩余现金约束。所有真实现金支出只来自 B。缺货损失 Σ_i s_i u_iω 是经济损失，不是现金采购，因此不进入预算。预算为不等式，unused_ω=B−C_Q−C_R−K_Fy_F−E_ω≥0 只作会计结果。

## 8. 唯一目标 T-COST

    min C_Q + C_R + K_F y_F + θ

满足每个场景：

    θ ≥ E_ω + Σ_i s_i u_iω.

Option fee 和应急支出各在目标中计一次，同时各在预算可行性约束中出现一次；这是同一现金流分别承担“经济成本”和“预算可行性”作用，不是目标内部重复计费。服务水平、CVaR、缺货量、unused budget 和 h 不是并列目标。

## 9. M0/M1/M2

### M0

固定 z_j0=1、z_jk=0(k≠0)，固定 y_F=0 和 g_iω=0；只优化 Quantity 及场景分配。C_R=0、C_F=0。

### M1

开放 z_jk，仍固定 y_F=0 和 g_iω=0；优化 Quantity+Reliability 及场景分配。

### M2

开放 z_jk 与 y_F；若购买 Option，Stage 2 可优化 g。它是论文主模型。

同一数据对象中必须程序化验证：M2(y_F=0)=M1，M1(z_j0=1)=M0。三模型共享 Ω、目标、成本分解、需求、履约与资源平衡。

## 10. Extensive Form 与 recourse

有限场景 Extensive Form 为每个 ω 建立一份 Stage 2 变量、资源平衡、Option 上限、场景预算和 θ 约束。

固定 Stage 1 解 x=(q,z,y_F) 后，场景 recourse value 为：

    Q_ω(x)=min E_ω + Σ_i s_i u_iω

满足第 6–7 节场景约束。u 保证相对完全补救。完整鲁棒值为：

    min_x C_Q(x)+C_R(x)+K_Fy_F + max_{ω∈Ω}Q_ω(x).

## 11. 单位与冻结测试

C_Q、C_R、K_F、E、B、s_i u_iω 和 θ 均为货币；q、g、served、u、h 为资源单位；ρ 无量纲。

必须测试：价格分量不重叠；p^F>0；场景预算正确；penalty 不进预算；两条平衡闭合；y_F=0 时 g=0；两个嵌套退化；Reliability 成本/履约单调；三模型场景 hash 相同。

## 12. N0 后参数用途与冻结门槛

- N2–N5 development/test fixtures：为单元测试、手算实例、EF=A0=A1 和异常路径测试设置的非科学参数；不得用于论文效应，也不得因表现理想自动升级。
- N6 pilot configuration：进入 N6 前登记的 pilot 专用参数、pilot seeds、运行时限和最大迭代，只验证计算规模、稳定性与 execution readiness；不得自动升级为 formal。
- N7 formal scientific parameters：Reliability 等级数、a/π、ρ 改善、K_F、F_bar、需求/风险范围、预算网格、有限 Ω、formal/validation/OOS seeds 及正式运行规则。冻结后供 N8 E2–E6 使用。

进入 N4 前另行冻结 E1 的目标一致性绝对/相对容差、C&CG gap/violation 标准、solver optimality 接受规则、A0 初始场景与 canonical tie-break。N7 不得重新定义 N4/N5 已冻结并用于正确性验证的标准。
