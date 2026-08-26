# LEGACY MIGRATION MANIFEST v1

状态：N1 provenance 记录。本文只登记通用工程迁移，不授权或实现 N2 科学模型。

## 1. 冻结来源

- legacy repository：`https://github.com/nieying-code/phrase3`
- legacy branch/tag：`main` / `v1.0-legacy-final`
- legacy commit：`d5a0eb7a623e2de831bdef1826fe2ec6240eee0f`
- legacy tree：`bdfa8542cea0fbac713a4145225c0eb326551a52`
- 核验的只读源：`D:\新建文件夹\项目交付\阶段3-4修复同步\phrase3`
- 迁移边界：`docs/LEGACY_REUSE_PLAN_v1.md`、只读 handoff 中的 `LEGACY_REUSE_MAP.md` 与 `NEW_PROJECT_HANDOFF.md`

旧仓库未作为 Git ancestor、submodule 或运行时依赖引入；未复制旧 `.git`、outputs、配置、正式 seeds、approval、registry、projection、论文文本或旧科学指纹。

## 2. 文件级 provenance

所有 `legacy_path` 均相对于冻结旧仓库。`classification` 采用已审计的 DIRECT REUSE / ADAPT；“复用”均指选择性重写和净化，不表示整文件复制。

| legacy_path | legacy source SHA-256 | classification | reused logic | removed legacy assumptions | new module path | new tests |
|---|---|---|---|---|---|---|
| `src/phase6_environment.py`; `src/environment_check.py` | `e9c595c370d33eed49005c5daa45c1c1ddcad120f6a27f592029be96d83536cf`; `c22880c85a820667819d20bba5851f166b8e4afec0205e90cbaba526b77eb86f` | DIRECT REUSE | 版本、接口、线程和许可证 fail-fast 检查；真实微型求解 | Phase 6 schema/hash、旧路径和实验语义 | `src/robust_budget_allocation/runtime/environment.py`; compatibility facade `src/robust_budget_allocation/environment.py` | `tests/test_runtime_environment.py`; `tests/test_environment_constants.py`; `tests/test_environment_gurobi.py` |
| `src/model_common.py` | `d478574b80b8c88318d7539642f1cb212135636c917bef1e11d1fc507d851b29` | ADAPT | `gurobi_direct` 选择、Threads 校验、终止状态规范化 | `ProcurementData`、inventory builder、库龄/处置/损耗及旧容差 | `src/robust_budget_allocation/runtime/solver.py` | `tests/test_solver_runtime.py` |
| `src/phase6_io.py` | `440de17364fc27b3d9ba663ff01fd7c121fbfb868c98900e123ece7b8a39fb09` | DIRECT REUSE | 同目录临时文件、replace、LF JSON/CSV、异常清理 | Phase 6 路径、结果 schema、旧 artifact 命名 | `src/robust_budget_allocation/io/atomic.py` | `tests/test_atomic_hashing.py` |
| `src/phase6_io.py`; `src/reproducibility.py` | `440de17364fc27b3d9ba663ff01fd7c121fbfb868c98900e123ece7b8a39fb09`; `19eed48331ce568ee5ba4a078981d454d06e4813d9ae109417a3fd6aadd006f3` | DIRECT REUSE | SHA-256、canonical JSON、LF 文本哈希 | 旧 fingerprint、approval、scenario identity 和输出 namespace | `src/robust_budget_allocation/io/hashing.py` | `tests/test_atomic_hashing.py` |
| `src/phase6_locking.py` | `f78c7ae077db7f5b291ccb6ca3a07faf4a0e32bf3f127fa8911f8f2434b836b7` | DIRECT REUSE | 有界等待的跨进程独占锁 | registry/projection 语义和 Phase 6 锁名 | `src/robust_budget_allocation/io/locking.py` | `tests/test_locking.py` |
| `src/reproducibility.py` | `19eed48331ce568ee5ba4a078981d454d06e4813d9ae109417a3fd6aadd006f3` | DIRECT REUSE | commit/tree、tracked dirty、required tracked inputs、untracked source gate | 旧 scenario generator、Phase 6 source roots、approval/artifact 规则 | `src/robust_budget_allocation/reproducibility/git_state.py` | `tests/test_git_reproducibility.py` |
| `src/reproducibility.py`; `src/phase6_io.py` | `19eed48331ce568ee5ba4a078981d454d06e4813d9ae109417a3fd6aadd006f3`; `440de17364fc27b3d9ba663ff01fd7c121fbfb868c98900e123ece7b8a39fb09` | DIRECT REUSE | 环境包版本、Git 身份、输入 hash、manifest 自身 hash | 旧 schema、旧场景/配置字段和旧指纹 | `src/robust_budget_allocation/reproducibility/manifests.py` | `tests/test_manifests.py` |
| `src/phase6_status.py` | `9dae96972fbcfb9d0d272d3efb7c2300a74f4f34ad26eceb8ef5b3ac373d105c` | DIRECT REUSE | 小型 status/heartbeat、终态、紧凑失败记录、原子写入 | Phase 6 状态名、进程扫描、registry/projection 和结果解析 | `src/robust_budget_allocation/runtime/status.py` | `tests/test_runtime_status.py` |
| `src/phase6_families.py` | `59e632b7aaebca006092ea2a3a8ae8a8f753efa3c2217613a48dca9b9fedc37b` | DIRECT REUSE | 离散经验样本的分数边界 upper-tail CVaR | 旧策略、旧风险参数、服务水平和正式结果口径 | `src/robust_budget_allocation/statistics/cvar.py` | `tests/test_statistics_helpers.py` |
| `src/phase6_m0_algorithm_performance_results.py`; `src/phase6_m2_algorithm_performance_formal.py` | `26316f428e400cce40e6ad1e634a0d47254863cf552c23bdfbdee54bd8631717`; `e380437c32575dd300efca848eac3fa04c1df2d2905dd0641ba013bf7a4f0bed` | DIRECT REUSE | 配对重采样、固定 RNG、percentile interval | 旧 seed、旧算法比较、旧估计量方向和正式实验 schema | `src/robust_budget_allocation/statistics/bootstrap.py` | `tests/test_statistics_helpers.py` |
| `tests/test_phase6_m2_formal_mechanism_results_audit.py`; `tests/test_phase6_m2_formal_extension_design.py`; `tests/test_phase6_m2_formal_oos_results_v1_1_audit.py` | `755849fc14de16b23542845cdacaf3a0a369977de6c7d561a5f0c1acc78f4652`; `d97eb3a5b0bc77f87afbfcde202ae0b8d2abe66e84242bfc3788da31a7bbec29`; `c0a02049ec88e229b093acb1170c0614a00d95c2489807a1ca4d44bbc6b7fcaa` | ADAPT | 通用 Holm adjusted p-values/rejections | 旧 hypothesis family、显著性结论和正式 p-values | `src/robust_budget_allocation/statistics/multiple_testing.py` | `tests/test_statistics_helpers.py` |
| `.github/workflows/ci.yml` | `ba994421657e2419643393420a1ea76899d0d59d4c379184a8ead5ff2a0f4fd7` | DIRECT REUSE | solver-free 与 licensed 测试分层 | 旧阶段、分支、命令、测试集合；禁止无许可证伪成功 | `.github/workflows/ci.yml` | GitHub Actions jobs `solver-free`, `gurobi-required` |

`runtime/`、`io/`、`reproducibility/`、`statistics/` 下的 `__init__.py` 是新项目 namespace glue，不包含 legacy logic。依赖锁仅加入上述通用实现实际需要的 `filelock==3.32.0` 和 `numpy==2.5.1`。

## 3. 明确未迁移

- REJECT：旧 scenario generator、C0/C1/T03、旧 beta、易腐库存、库龄、holding/disposal/expiry/loss/residual value、旧 M1/M2/M2.1、旧储备 R、正式矩阵/seeds/results、论文与审批材料。
- REFERENCE ONLY：旧 SPW-C&CG 未被改名或迁移为 A1。
- N1 deferred ADAPT：数据类、recourse、extensive form、exact oracle、Standard C&CG、scenario pool、runner、seed management、OOS、registry/projection。它们只能在 N2–N5 依照新接口另行设计。

## 4. 审计与完整性

新项目迁移文件的 SHA-256 由 `docs/N1_MIGRATION_HASHES.sha256` 记录。该清单在最终测试和审计后生成；N0 的 `docs/N0_DESIGN_HASHES.sha256` 保持不变。
