# Tasks: A 端面质量分层与批量评估

**Input**: Design documents from `/specs/004-quality-policy-batch/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: 用户明确要求覆盖参考图和 A2 抽样复现，因此各故事先写测试。

## Phase 1: Setup

- [x] T001 固化本机 A2 无图反馈证据于 `specs/004-quality-policy-batch/evidence/a2-local-user-summary.json`
- [x] T002 [P] 增加默认定位质量策略于 `config/end_face_quality.example.json`
- [x] T003 [P] 更新质量配置与有效性治理语义于 `config/README.md`、`.specify/memory/constitution.md`

## Phase 2: Foundational

- [x] T004 定义 v2 单图结果 Schema 于 `contracts/a-end-face-result.schema.json`
- [x] T005 [P] 定义质量策略 Schema 于 `contracts/a-end-face-quality-policy.schema.json`
- [x] T006 [P] 定义批量汇总 Schema 于 `contracts/a-end-face-batch-quality-summary.schema.json`
- [x] T007 更新严格 JSON 和 v2 不变量于 `algorithms/end_face/contract.py`

## Phase 3: User Story 1 - 定位与测量质量分层 (Priority: P1)

**Goal**: 定位成功不再被无关特征否决，同时不修改任何核心特征质量状态。

**Independent Test**: 有效变换加无效 19/30 必须得到定位有效、测量不完整和原始特征无效。

- [x] T008 [P] [US1] 先增加定位/特征分层测试于 `tests/test_end_face_quality.py`
- [x] T009 [US1] 实现策略加载和定位检查于 `algorithms/end_face/quality.py`
- [x] T010 [US1] 实现不可改写的逐特征状态和测量完整性于 `algorithms/end_face/quality.py`
- [x] T011 [US1] 实现复用参考模型的端面适配器于 `algorithms/end_face/adapter.py`
- [x] T012 [US1] 接入质量策略和 v2 输出于 `algorithms/end_face/main.py`

## Phase 4: User Story 2 - 质量来源可追溯诊断 (Priority: P2)

**Goal**: 逐项说明 19、30、46、M78、80、86 的核心路径、固定条件和实际质量字段。

**Independent Test**: 参考图诊断必须定位 19/30 短线来源，A2 涉及的其他来源必须有固定条件目录。

- [x] T013 [P] [US2] 先增加核心原因目录和参考资产测试于 `tests/test_end_face_quality.py`
- [x] T014 [US2] 实现核心质量来源诊断目录于 `algorithms/end_face/quality.py`
- [x] T015 [US2] 将诊断对象加入单图特征质量契约于 `algorithms/end_face/contract.py`
- [x] T016 [US2] 更新单图契约与迁移说明于 `README.md`、`specs/004-quality-policy-batch/contracts/a-end-face-result-v2.md`

## Phase 5: User Story 3 - 外置数据批量质量评估 (Priority: P3)

**Goal**: 对外置 Manifest 图片批量执行并支持脱图 JSONL 重统计。

**Independent Test**: 25 条合成结果必须精确复现 A2 计数；篡改 Manifest 必须在核心调用前失败。

- [x] T017 [P] [US3] 先增加 A2 25 条计数和确定性汇总测试于 `tests/test_end_face_batch.py`
- [x] T018 [P] [US3] 先增加 Manifest 篡改预检测试于 `tests/test_end_face_batch.py`
- [x] T019 [US3] 实现结果聚合、来源/原因分布和耗时统计于 `tools/evaluate_end_face_batch.py`
- [x] T020 [US3] 实现 Manifest 批量检测及结果 JSONL 输出于 `tools/evaluate_end_face_batch.py`
- [x] T021 [US3] 实现无图片 JSONL 重统计子命令于 `tools/evaluate_end_face_batch.py`
- [x] T022 [US3] 更新外置数据和批量运行文档于 `data/README.md`、`specs/004-quality-policy-batch/quickstart.md`

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T023 更新现有 CLI/契约测试到 v2 于 `tests/test_end_face_cli.py`、`tests/test_end_face_contract.py`
- [x] T024 运行参考图、全量 unittest、Schema、核心哈希和 Git 大文件门禁
- [x] T025 核对 SpecKit 需求覆盖并完成 `specs/004-quality-policy-batch/tasks.md`

## Dependencies & Execution Order

- Setup 无依赖；Foundational 依赖 Setup 并阻塞所有用户故事。
- US1 建立状态模型，是 US2 契约诊断和 US3 汇总的前置。
- US2 与 US3 在 US1 后可并行；Polish 依赖三者完成。
- 同一文件内任务按编号顺序执行；标记 `[P]` 的任务只涉及不同文件。

## Parallel Opportunities

- T002/T003 可并行；T005/T006 可并行。
- T013 与 T017/T018 可在 US1 完成后并行。
- 文档 T016 与批量实现 T019-T021 可并行。

## Implementation Strategy

MVP 为 US1：先让单图结果正确分离定位和测量质量；随后增加诊断，再增加批量统计。所有测试任务先于
对应实现执行，完成后将本文件任务逐项标记为 `[x]`。
