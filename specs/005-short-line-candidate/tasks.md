# Tasks: A 端面短线候选诊断与测量改进

**Input**: Design documents from `/specs/005-short-line-candidate/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: 本增量明确要求 TDD、参考资产、合成失败保护、Schema、核心来源和大文件门禁；每个故事先写测试并确认失败。

**Organization**: 任务按三个用户故事分组；19/30 诊断是 MVP，候选量测和外置 A2 比较分别可独立验收。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可在不同文件上并行，不依赖同阶段未完成任务
- **[Story]**: 对应 spec.md 的 US1、US2、US3
- 每项都包含具体文件路径和关联的核心规格范围

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 冻结无图证据、数据边界和现有核心来源。

- [X] T001 Record the user-reported A2 v2 25-image baseline and its server-access limitation in `specs/005-short-line-candidate/evidence/a2-v2-first-25-user-summary.json`
- [X] T002 Verify image/archive/runtime JSONL and Python cache exclusions remain explicit in `.gitignore`
- [X] T003 Pin the desktop/repository core SHA-256 and v2 baseline invariants in `tests/test_end_face_reference.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 固定候选的版本、通用严格 JSON 和旧结果兼容边界，阻塞所有故事实现。

- [X] T004 Add failing configuration validation and canonical feature identity tests in `tests/test_short_line_candidate.py`
- [X] T005 Add shared candidate configuration fixture helpers without image assets in `tests/end_face_test_support.py`
- [X] T006 Define the versioned candidate configuration values in `config/end_face_short_line_candidate.v1.json`
- [X] T007 Implement configuration parsing, finite-number validation, canonical hashing and supported-feature checks in `algorithms/end_face/short_line_candidate.py`

**Checkpoint**: 配置错误能安全失败，候选只接受规范 19/30，核心未被调用或修改。

---

## Phase 3: User Story 1 - 逐图解释 19 与 30 的失败 (Priority: P1) 🎯 MVP

**Goal**: 从旧核心量测和外置图片复算 19/30 的 ROI、对比度、梯度、峰值、边界及明确回退分类。

**Independent Test**: 合成清晰/空白/边界/双峰图得到预期诊断；参考图复现 19/30 内部峰但固定显著性失败。

### Tests for User Story 1

- [X] T008 [P] [US1] Add failing synthetic ROI/core-profile diagnostics tests for clear, blank, boundary and competing peaks in `tests/test_short_line_candidate.py`
- [X] T009 [P] [US1] Add failing accessible-reference assertions for 19/30 core source, ROI statistics, peak, threshold and fallback reason in `tests/test_end_face_quality.py`

### Implementation for User Story 1

- [X] T010 [US1] Implement immutable core measurement extraction and raw/canonical 19/30 matching in `algorithms/end_face/short_line_candidate.py`
- [X] T011 [US1] Implement oriented ROI sampling, contrast/gradient statistics and exact core short-line profile reconstruction in `algorithms/end_face/short_line_candidate.py`
- [X] T012 [US1] Implement machine-countable core-path consistency, no-edge, boundary-peak and low-prominence diagnostics in `algorithms/end_face/short_line_candidate.py`
- [X] T013 [US1] Preserve the reference diagnostic observations and A2 JSONL field mapping in `specs/005-short-line-candidate/research.md`

**Checkpoint**: 不运行候选恢复也能独立解释参考/合成失败；所有诊断只读旧核心结果。

---

## Phase 4: User Story 2 - 独立短线候选真实测量 (Priority: P2)

**Goal**: 依据参考梯度和目标图像联合重估短线位置/方向，以独立多门禁状态与旧核心逐图并列。

**Independent Test**: 合成偏移/旋转线达到位置/方向误差要求；低对比、边界、双峰安全失败；启用候选前后旧结果深度相等。

### Tests for User Story 2

- [X] T014 [P] [US2] Add failing subpixel position/orientation recovery and blank/low-contrast/boundary/ambiguous rejection tests in `tests/test_short_line_candidate.py`
- [X] T015 [P] [US2] Add failing v3 result and independent transition tests in `tests/test_end_face_contract.py`, plus core-output immutability tests in `tests/test_short_line_candidate.py`
- [X] T016 [P] [US2] Add failing single-image CLI candidate JSON and invalid-config tests in `tests/test_end_face_cli.py`
- [X] T017 [P] [US2] Add failing result/config JSON Schema validation tests in `tests/test_end_face_schemas.py`

### Implementation for User Story 2

- [X] T018 [US2] Implement vectorized coarse-to-fine reference-gradient orientation/longitudinal/lateral registration in `algorithms/end_face/short_line_candidate.py`
- [X] T019 [US2] Implement coverage, contrast, gradient, correlation, robust-prominence, separated-peak, boundary and finite-geometry gates in `algorithms/end_face/short_line_candidate.py`
- [X] T020 [US2] Build target/reference candidate geometry, core deltas and four-state transitions without mutating baseline objects in `algorithms/end_face/short_line_candidate.py`
- [X] T021 [US2] Run the optional candidate after immutable core detection and preserve before/after baseline equality in `algorithms/end_face/adapter.py`
- [X] T022 [US2] Upgrade the strict single-image contract to `a-end-face-result/3` with nullable candidate provenance and `shortLineCandidates` in `algorithms/end_face/contract.py`
- [X] T023 [P] [US2] Define machine-readable candidate configuration and v3 result contracts in `contracts/a-end-face-short-line-candidate-config.schema.json` and `contracts/a-end-face-result.schema.json`
- [X] T024 [US2] Add `--short-line-candidate-config` and v3 output wiring in `algorithms/end_face/main.py`
- [X] T025 [US2] Verify reference 19/30 diagnostics/candidates and immutable core fields end-to-end in `tests/test_end_face_quality.py`

**Checkpoint**: 候选能改变有图像证据的几何与独立状态，但 coreValid、旧量测、定位和旧完整性完全不变。

---

## Phase 5: User Story 3 - 外置 A2 批量逐图对照 (Priority: P3)

**Goal**: 用外置 Manifest、图片和 v2/v3 JSONL 生成逐图比较及可无图重建的确定性汇总。

**Independent Test**: 临时 Manifest/图片/基线结果验证一一匹配、预检拒绝、恢复/退化聚合和两次汇总一致。

### Tests for User Story 3

- [X] T026 [P] [US3] Add failing Manifest/task/hash preflight and v2/v3 baseline comparison tests in `tests/test_short_line_comparison.py`
- [X] T027 [P] [US3] Add failing transition, 46/M78/80/86 baseline and deterministic resummary tests in `tests/test_short_line_comparison.py`
- [X] T028 [P] [US3] Add failing comparison-record and batch-summary Schema tests in `tests/test_end_face_schemas.py`

### Implementation for User Story 3

- [X] T029 [US3] Implement all-input preflight, unique task mapping and baseline version validation in `tools/compare_short_line_candidates.py`
- [X] T030 [US3] Implement per-image candidate comparison JSONL and baseline-failure records in `tools/compare_short_line_candidates.py`
- [X] T031 [US3] Implement image-free deterministic summary with transition, delta, failure-check and priority-feature distributions in `tools/compare_short_line_candidates.py`
- [X] T032 [P] [US3] Define machine-readable comparison and summary contracts in `contracts/a-end-face-short-line-comparison.schema.json` and `contracts/a-end-face-short-line-batch-summary.schema.json`
- [X] T033 [US3] Add optional candidate configuration to external Manifest detection while retaining quality-summary semantics in `tools/evaluate_end_face_batch.py`
- [X] T034 [US3] Document exact external A2 compare/resummary commands and no-image boundaries in `README.md` and `specs/005-short-line-candidate/quickstart.md`

**Checkpoint**: Mac 可直接对现有 v2 结果与外置 A2 重跑；服务器可用临时资产验证相同合同，不产生 A2 结论。

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 完成全部门禁并使规格、合同、实现、测试可追溯。

- [X] T035 [P] Update package/algorithm version and candidate behavior summary in `pyproject.toml` and `README.md`
- [X] T036 Mark every completed task and verify FR/SC traceability in `specs/005-short-line-candidate/tasks.md`
- [X] T037 Run the complete unittest suite from `tests/` and fix all regressions
- [X] T038 Run all four changed/new JSON Schemas against representative success, failure and summary payloads through `tests/test_end_face_schemas.py`
- [X] T039 Compare `algorithms/end_face/core.py` byte-for-byte and SHA-256 with the desktop archive source
- [X] T040 Audit tracked files for images, archives, JSONL and files larger than 5 MiB, then verify `git diff --check`
- [X] T041 Execute the server reference/synthetic scenarios in `specs/005-short-line-candidate/quickstart.md` and record only non-image evidence

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 可立即执行。
- **Foundational (Phase 2)**: 依赖 Setup；候选配置验证阻塞所有故事。
- **US1 (Phase 3)**: 依赖 Foundation，是诊断 MVP。
- **US2 (Phase 4)**: 依赖 US1 的 ROI/coreSearch 诊断；候选门禁复用同一观测。
- **US3 (Phase 5)**: 依赖 US2 的 FeatureComparison；输入预检和汇总测试可先写失败。
- **Polish (Phase 6)**: 依赖三个故事全部完成。

### User Story Dependencies

- **US1 (P1)**: Foundation 后独立完成，单独交付只读诊断价值。
- **US2 (P2)**: 依赖 US1 的诊断采样，但不依赖批量工具。
- **US3 (P3)**: 依赖 US2 的候选比较结构；不会修改 US1/US2 算法。

### Within Each User Story

- 测试任务必须先执行并确认因缺少对应模块/合同而失败。
- 配置/实体验证先于搜索服务，搜索先于 adapter/CLI 集成。
- 每个阶段 checkpoint 通过后才进入下一故事。
- 同一文件上的任务严格按编号顺序执行。

### Parallel Opportunities

- T008 与 T009 可在不同测试文件并行。
- T014–T017 可先在四个测试面并行编写失败测试。
- T023 可在 T018–T020 稳定数据形状后与 adapter 集成并行。
- T026–T028 可并行编写批量/Schema 失败测试。
- T032 可在 T029–T031 数据形状固定后独立完成。
- T035 可与不修改 README/pyproject 的门禁准备并行。

---

## Parallel Example: User Story 2

```text
Task T014: synthetic candidate recovery/rejection tests in tests/test_short_line_candidate.py
Task T015: v3/immutability tests in tests/test_end_face_contract.py
Task T016: CLI tests in tests/test_end_face_cli.py
Task T017: Schema tests in tests/test_end_face_schemas.py
```

## Parallel Example: User Story 3

```text
Task T026: preflight/baseline tests in tests/test_short_line_comparison.py
Task T027: aggregation/resummary tests in tests/test_short_line_comparison.py
Task T028: record/summary Schema tests in tests/test_end_face_schemas.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Setup 和 Foundation。
2. 先运行 T008/T009，确认测试因诊断不存在而失败。
3. 完成 T010–T013，仅交付可追溯的 ROI/coreSearch 诊断。
4. 验证参考图与合成样本，不改变任何核心输出。

### Incremental Delivery

1. US1：先能解释 19/30 为什么失败。
2. US2：再增加有失败保护的独立候选和 v3 单图合同。
3. US3：最后增加 Mac 外置真实 A2 逐图比较和无图汇总。
4. 全部通过后执行 SpecKit `analyze` 只读交叉检查，再提交推送。

## Notes

- `[P]` 仅用于不同文件或稳定接口后的独立工作。
- 真实 A2 未在服务器提供时，T041 只能记录“需要 Mac 重跑”，不能勾选真实恢复 SC-004 为已验证。
- `recovered` 是候选与核心的对照状态，不是产品 OK/NG。
- 禁止修改 `algorithms/end_face/core.py` 或把候选结果写回旧字段。
