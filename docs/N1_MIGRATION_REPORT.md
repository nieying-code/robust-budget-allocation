# N1 MIGRATION REPORT

## 1. 结论

N1 只迁移并净化了与旧科学模型无关的通用工程能力。N0 冻结设计未修改；M0/M1/M2、A0/A1、场景生成、pilot 与正式实验均未实现或运行。

## 2. 实际迁移

- runtime：锁定环境 preflight、真实 Gurobi license/optimizer 微型求解、`gurobi_direct`/Threads=1 校验、通用 solver status、failure/status/heartbeat。
- I/O：原子 text/JSON/CSV 写入、异常清理、SHA-256、canonical JSON、跨进程锁。
- reproducibility：Git commit/tree、clean tracked tree、untracked scientific input、required tracked input 和 source manifest。
- statistics：经验 upper-tail CVaR、固定 PCG64 的 paired percentile bootstrap、Holm multiple-testing helper。
- CI：solver-free hosted job；只有显式启用且具有真实 Gurobi 13 标签/许可证的 self-hosted runner 才运行 licensed job，不 fallback、不伪造成功。

完整文件级来源、净化内容和测试见 `docs/LEGACY_MIGRATION_MANIFEST_v1.md`。

## 3. 未迁移

所有旧科学场景、参数、库存、模型、算法和结果资产均未迁移。N1 也未实现需按新科学接口适配的数据类、recourse、extensive form、oracle、A0、scenario pool、runner、seed registry、OOS 或 projection；这些属于 N2–N5 的后续门槛工作。旧 SPW-C&CG 未进入新项目。

## 4. 环境 preflight

本地正式检查结果：

- Python `3.12.10` / CPython
- Pyomo `6.10.1`
- gurobipy `13.0.2`
- Gurobi Optimizer `13.0.2`
- interface `gurobi_direct`
- Threads `1`
- license available：`true`
- preflight：`PASS`

任何版本、接口、Threads 或 license 不匹配均 fail fast；没有其他 solver fallback。

`ensure_preflight_once()` 在进程内仅缓存成功结果：第一次 `solve_model()` 前执行完整版本/interface/Threads/license 微型求解，失败不会缓存；后续 solver 构造不重复微型求解。求解计时从 solver 构造完成后开始，因此后续 A0/A1 timing 不会包含重复 license preflight。

Exact 状态认证要求 solver status 为 `ok`，且 termination 只能是 `optimal` 或 `globallyOptimal`。`locallyOptimal` 单独报告为 `locally_optimal`；solver `error` 优先报告 `solver_error`，即使 termination 声称 optimal；非可接受 status 与 exact termination 的组合报告 `invalid_solver_status`；`maxIterations` 与 `maxTimeLimit` 分别报告 `iteration_limit` 与 `time_limit`。

## 5. 测试与 CI

- solver-free local：`46 passed, 2 deselected`
- licensed local：`2 passed, 46 deselected`，使用真实 Gurobi license
- 覆盖环境成功/失败、solver mismatch、Threads mismatch、严格 solver/termination 联合映射、连续求解只执行一次 preflight、atomic/interrupted write、hash/canonical JSON、Git clean/dirty/untracked、commit/tree manifest、locking conflict/stale file、CVaR、paired bootstrap 固定 RNG/edge cases、Holm、status lifecycle。
- N1 hash 清单测试强制冻结路径集合完全相等，拒绝缺项、重复、绝对路径和 `..`，并检查普通文件存在性与逐项 SHA-256。Git commit/tree 作为清单外部锚点。
- CI `solver-free` 可在无 Gurobi license 的 hosted runner 执行；`gurobi-required` 仅在仓库变量显式启用并匹配 `[self-hosted, windows, gurobi-13]` runner 时执行真实 licensed tests。

## 6. 科学泄漏审计

审计范围为新加入的 `src/` 实现、tests、CI 和依赖声明。未发现旧 Phase 6 namespace、旧 C0/C1/T03 或 beta 公式、旧库存/库龄/处置/过期/损耗模型、旧正式 config/seeds/results、旧 M1/M2/M2.1 实现或 SPW→A1 改名。文档仅为 provenance 和明确排除项而提及这些词。

## 7. N2 readiness

通用工程底座具备进入 N2 的技术条件，当前没有 N2 blocker；但只有 Draft PR #2 经用户批准并合并后才可进入 N2。在此之前停止，不实现模型。
