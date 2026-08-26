# LEGACY REUSE PLAN v1

状态：N0 最终复用边界。本文不授权 N1；Draft PR #1 未合并前禁止迁移。

## 1. Provenance 与边界

- 冻结仓库：`https://github.com/nieying-code/phrase3`
- branch：`main`
- commit：`d5a0eb7a623e2de831bdef1826fe2ec6240eee0f`
- tree：`bdfa8542cea0fbac713a4145225c0eb326551a52`
- tag：`v1.0-legacy-final`
- 已核验本地源：`D:\新建文件夹\项目交付\阶段3-4修复同步\phrase3`，HEAD=`d5a0eb7a623e2de831bdef1826fe2ec6240eee0f`、tree=`bdfa8542cea0fbac713a4145225c0eb326551a52`，与冻结身份一致。另两个 checkout 分别停在 `b13f13b...` 和 `461a22d...`，不得作为冻结迁移源。
- 交接材料：`D:\新建文件夹\项目：robust-budget-allocation\00_legacy_freeze`（只读）。

新仓库不复制旧 `.git`、outputs、结果、配置、正式种子、approval、registry、projection、论文文本或科学指纹。每个迁移文件应在新仓库记录 `legacy_path`、`legacy_commit`、分类、净化说明和新测试。

## 2. DIRECT REUSE

| 资产 | 旧来源 | 新项目动作 | 验收 |
|---|---|---|---|
| Gurobi 参数校验 | `src/model_common.py`、runner YAML | 抽取接口/Threads/状态检查；数值容差重新冻结 | 错版本、接口、线程、license 均 fail fast |
| 环境验证框架 | `src/phase6_environment.py`, `src/environment_check.py` | 改为新 schema 与版本锁，不继承旧 hash | 本地真实求解通过，CI 无 license 时不伪造 |
| Git/source 验证 | `src/reproducibility.py` | 改新 repo 输入根与 artifact 规则 | dirty/untracked input 测试 |
| 原子 I/O | `src/phase6_io.py` | 去 Phase 6 命名后迁移 | Windows 异常/哈希测试 |
| 跨进程锁 | `src/phase6_locking.py` | 迁移到通用模块 | 并发与 stale lock 测试 |
| CVaR 纯函数 | `src/phase6_families.py` | 只迁移纯统计实现和独立向量测试 | 边界权重重算一致 |
| bootstrap/statistics | M2 OOS/algorithm results modules | 抽取配对、聚类 bootstrap 与 Holm 工具 | 新估计量、新 seed registry |
| audit/hash | `src/reproducibility.py`, `src/phase6_io.py` | 新 namespace/schema/hash | 篡改检测 |
| status 工具 | `src/phase6_status.py` | 合并重复版本 | 不解析大型结果即可读状态 |
| CI 骨架 | `.github/workflows/ci.yml` | 仅借骨架；新命令/依赖/标记 | solver-free 与 licensed tests 分离 |

“Direct”表示工程逻辑可复用，不表示未经 review 原样复制，也不继承科学结论。

## 3. ADAPT

| 资产 | 旧来源 | 适配要求 |
|---|---|---|
| 数据类 | `src/model_data.py` | 新建 `BudgetAllocationData`；删除旧易腐/救灾默认字段 |
| recourse/evaluation | `src/recourse_model.py`, `src/evaluation.py` | 保留固定 first-stage→场景 LP 接口；重写 Q/R/F 会计 |
| extensive form | `src/extensive_model.py` | builder 注入新变量和约束；不 import 旧 inventory builder |
| exact oracle | 同上 | 保留完整认证原则；新场景与补救函数 |
| Standard C&CG | `src/ccg.py` | MP/oracle/scenario ID 显式依赖注入；新停止状态 |
| scenario pool 容器 | `src/spw_ccg.py` | 只保留有序去重思想；加入来源、生命周期、认证 epoch |
| runner lifecycle | `src/phase6_runner.py` 等 | 拆成小型通用组件；新授权/namespace |
| seed management | `src/phase6_protocol.py` | 建新种子集合且验证 train/pilot/formal/OOS 不相交 |
| OOS framework | M2 formal OOS modules | 保留冻结策略、CRN 和禁止测试集重优化；重写指标 |
| tests | `tests/` | 迁移测试思想；删除旧结果目录时态断言和科学断言 |
| service level | family/OOS modules | 只参考计算思想；按新 served/u 定义重写为评价指标，不进入目标 |

## 4. REFERENCE ONLY

- `src/phase6_m2.py`：只参考共享潜变量与分量 hash；不得继承履约公式、C0/C1/T03。
- `src/spw_ccg.py`：作为历史 baseline/组件参考；不能成为 A1 创新本身。
- 旧库存与 service-level 定义：只用于理解实现风险；新项目已冻结单期非易腐，并以新 served/u 定义评价服务。
- 旧正式结果与论文：只用于背景和 baseline provenance，不进入新项目证据或 README 宣传。

## 5. REJECT

- `src/scenario_generator.py` 与旧科学生成公式。
- `build_inventory_model`/`inventory_model.py` 及全部库龄、持有、处置、过期、残值结构；首版已冻结为单期非易腐。
- 旧 M1 采购能力上限、M2.1 端点选择。
- 所有旧 outputs、正式种子、审批、配置版本、registry、projection、图表、论文结论。
- 旧 `.git`、branch 和历史。

## 6. 迁移流程

只有 Draft PR #1 经用户批准并合并后才可启动 N1。N1 建立 provenance manifest，逐模块复制—净化—review—单测；每次只迁移一类通用能力。先 I/O、环境、hash、统计，后数据接口、recourse/extensive/A0，最后 runner/OOS。A1 只在 A0 正确性冻结且其 scoring/memory 规范在 N5 前冻结后新写。

## 7. 当前审计结论

本阶段仓库中的 preflight 和 CI 是按照交接原则重新实现的最小代码，并非整仓复制。冻结本地源已核验，但目前仍不声称任何旧源文件已被迁移；N1 迁移时须逐文件登记 provenance。
