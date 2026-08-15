# Tasks: 全画面壳体外圆唯一定位

**Input**: Design documents from `specs/004-full-frame-circle-localization/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: 本功能按用户要求和Constitution采用TDD；每个实现任务前必须先运行对应失败测试。

## Phase 1: Setup and Baseline

**Purpose**: 冻结修改前证据与仓库边界。

- [x] T001 Record the clean branch, 98-test baseline (95 passed, 3 optional-jsonschema skipped), full-frame 0/25, ROI 25/25, groove 25/25 and subpixel 21/25 facts in `specs/004-full-frame-circle-localization/evidence/baseline-summary.json`
- [x] T002 Verify existing Python ignore/media/large-file protections and record that no new dependency is required in `specs/004-full-frame-circle-localization/research.md`

---

## Phase 2: Foundational Contracts

**Purpose**: 在算法实现前冻结配置、错误码、诊断和真实标注契约。

- [x] T003 [P] Add failing strict-config tests for locator version, finite ranges, candidate limits, ROI mutual exclusion and single-mode scope in `tests/test_slot_pose_contract.py`
- [x] T004 [P] Add failing Schema tests for locator config/diagnostics and new fail-closed error codes in `tests/test_slot_pose_cli.py` and `tests/test_slot_pose_contract.py`
- [x] T005 [P] Add failing real-case annotation tests for missing/draft/algorithm-prefill/hash mismatch, variable point counts and reviewed eligibility in `tests/test_real_case_annotations.py`
- [x] T006 Implement versioned locator configuration validation and error-code compatibility in `algorithms/slot_pose/full_frame_circle_locator.py`, `algorithms/slot_pose/contract.py` and `contracts/slot-pose-config.schema.json`
- [x] T007 Implement the reviewed real-case annotation index/comparison schemas in `contracts/slot-pose-annotation.schema.json` and `contracts/real-case-annotation-index.schema.json`

**Checkpoint**: 配置和标注契约可独立验证，尚未改变运行时定位。

---

## Phase 3: User Story 1 - 从整幅图像唯一锁定壳体 (Priority: P1) MVP

**Goal**: 从全画面产生有限候选，只让唯一且通过gyj物理圆门的壳体进入下游。

**Independent Test**: 受控图像覆盖唯一壳体、强工装、无圆、相近双圆、遮挡、裁切和候选溢出；同一25张全画面最终圆与ROI成对比较。

### Tests for User Story 1

- [x] T008 [P] [US1] Add failing Otsu/component proposal tests for brightness, noise, translation, scale, crop, border contact and nonfinite input in `tests/test_full_frame_circle_locator.py`
- [x] T009 [P] [US1] Add failing sparse-gyj delegation, score, dedup, no-candidate, overflow and ambiguous-two-circle tests in `tests/test_full_frame_circle_locator.py`
- [x] T010 [P] [US1] Add failing adapter integration tests proving locator failure stops profile/groove/angle and never falls back to legacy/zero/stale values in `tests/test_legacy_adapter.py` and `tests/test_single_real_groove.py`
- [x] T011 [P] [US1] Add failing backward-compatibility tests for explicit ROI, disabled locator, legacy and paired modes in `tests/test_legacy_adapter.py` and `tests/test_paired_slot_pose.py`

### Implementation for User Story 1

- [x] T012 [US1] Implement bounded low-resolution Otsu thresholds, connected components and explainable component proposals in `algorithms/slot_pose/full_frame_circle_locator.py`
- [x] T013 [US1] Implement 180-ray locked-gyj assessment, score components, physical-circle dedup and unique best/second selection in `algorithms/slot_pose/full_frame_circle_locator.py`
- [x] T014 [US1] Delegate the unique winner to the existing 720-ray final physical-circle gate without weakening thresholds in `algorithms/slot_pose/full_frame_circle_locator.py` and `algorithms/slot_pose/physical_outer_circle.py`
- [x] T015 [US1] Integrate the full-frame strategy before groove recognition for `single_real_groove`, preserve explicit ROI behavior and emit stable failures in `algorithms/slot_pose/legacy_adapter.py`
- [x] T016 [US1] Add reusable loaded-adapter execution and batch reuse while preserving per-image asset verification in `algorithms/slot_pose/main.py` and `tools/run_slot_pose_batch.py`
- [x] T017 [US1] Add the disabled-by-default locator example and strict user documentation in `config/inspection.example.json` and `config/README.md`

**Checkpoint**: User Story 1可在合成和单图真实输入上独立运行；非唯一圆不能进入槽阶段。

---

## Phase 4: User Story 2 - 审阅候选与逐图人工标注对照 (Priority: P2)

**Goal**: 每个真实验收样本都有人工参考状态，审阅者能同时看到标注值、检测值和差值。

**Independent Test**: 已复核样本生成圆心/半径/槽角逐图差值和同屏叠加；其余样本生成待标注模板并使严格准确率验收失败。

### Tests for User Story 2

- [x] T018 [P] [US2] Add failing tests for path-safe empty LabelMe templates, annotation index completeness and no truth prefill in `tests/test_real_case_annotations.py`
- [x] T019 [P] [US2] Add failing tests for reviewed circle/open-groove parsing, circular angle difference, quadrant and null-on-failure comparison in `tests/test_real_case_annotations.py`
- [x] T020 [P] [US2] Add failing review tests for component/circle candidate overlays and human-vs-automatic color separation in `tests/test_slot_pose_review.py`
- [x] T021 [P] [US2] Add failing summary tests for localization status, best/second margin, full-vs-ROI circle deltas, annotation coverage and pending counts in `tests/test_slot_pose_diagnostic_summary.py`

### Implementation for User Story 2

- [x] T022 [US2] Implement Git-external annotation index and blank LabelMe template generation without algorithm truth leakage in `tools/prepare_real_case_annotations.py`
- [x] T023 [US2] Implement strict reviewed-annotation validation and per-image human-vs-automatic circle/groove comparison in `tools/evaluate_annotated_real_cases.py`
- [x] T024 [US2] Render all localization proposals, sparse circles, final circle, human circle/groove and automatic circle/groove with a fixed legend in `tools/render_slot_pose_review.py`
- [x] T025 [US2] Summarize localization candidates, failure causes, stage timing, full-vs-ROI deltas and annotation coverage in `tools/summarize_slot_pose_diagnostics.py`
- [x] T025A [US2] Report per-condition static repeatability from circular detection-minus-truth residuals, and return `NOT_EVALUATED` for unconfirmed grouping, insufficient repeats or incomplete reviewed truth in `tools/evaluate_annotated_real_cases.py`
- [x] T026 [US2] Generate an index and Git-external blank templates for all 25 JPEGs, never overwrite the separate same-source BMP annotation or treat it as JPEG truth, and record only de-identified reviewed/pending counts in `specs/004-full-frame-circle-localization/evidence/annotation-coverage-summary.json`

**Checkpoint**: 已标注样本可评估；未标注24张明确显示pending，不能进入准确率统计。

---

## Phase 5: User Story 3 - 保留ROI与下游兼容性 (Priority: P3)

**Goal**: 新定位策略增量启用，既有ROI、v2、legacy、paired、single-groove和PLC安全边界无回退。

**Independent Test**: 全量单元/Schema/CLI/批量、历史72角、paired正负和25张ROI基线全部复跑。

### Tests and Integration for User Story 3

- [x] T027 [US3] Update backward-compatible diagnostic/result Schema coverage in `contracts/slot-pose-result.schema.json`, `tests/test_slot_pose_cli.py` and `tests/test_slot_pose_review.py`
- [x] T028 [US3] Update project and 004 validation documentation, including 25-image/3-BMP/1-reviewed-label facts and no production-accuracy claim, in `README.md` and `specs/004-full-frame-circle-localization/quickstart.md`
- [x] T029 [US3] Run legacy 72-angle and paired positive/negative regressions and record de-identified numeric evidence in `specs/004-full-frame-circle-localization/evidence/compatibility-summary.json`

**Checkpoint**: 所有既有消费者和模式保持兼容。

---

## Phase 6: Real-data Validation and Polish

**Purpose**: 用外置25张证明第一优先级开发门，检查性能、污染和剩余阻塞。

- [x] T030 Run full-frame and frozen-ROI batches on the same external 25-image manifest, generate external overlays/contact sheets/JSONL, and commit only de-identified statistics in `specs/004-full-frame-circle-localization/evidence/full-frame-vs-roi-summary.json`
- [x] T031 Measure cold/steady stage P50/P95/max, batch wall throughput and peak RSS on the recorded server in `specs/004-full-frame-circle-localization/evidence/performance-summary.json`
- [x] T032 Run focused tests, the full unittest suite, explicit jsonschema gate, CLI help/compile gates and quickstart checks, then mark all completed tasks in `specs/004-full-frame-circle-localization/tasks.md`
- [x] T033 Run `git diff --check`, JSON parsing, media/archive/large-file/private-path pollution checks and verify both forbidden workspaces remain untouched
- [x] T034 Run final read-only Spec Kit consistency analysis across `spec.md`, `plan.md` and `tasks.md`, resolving any critical/high inconsistency before commit
- [x] T035 Create a local incremental commit on `003-a2-paired-notch-stability` without push or merge, and record the commit plus remaining data/quality/PLC blockers in the final report

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 → US2 → US3 → Phase 6。
- T003～T005可并行设计，但实现按T006、T007顺序落地。
- US1必须先完成，因为US2的自动结果和US3兼容验证依赖新定位诊断。
- T018～T021为不同测试文件可并行；T022～T025按数据契约、比较、渲染、汇总顺序执行。
- T026只生成Git外模板和脱敏计数，不等待人工完成25张同图JPEG标注；人工复核是外部验收BLOCKED项。
- T030真实数据通过后才能执行性能结论T031；最终门T032～T035顺序执行。

## Implementation Strategy

1. 先交付US1：解决全画面错误锁圆，同时严格失败关闭。
2. 再交付US2：让每个真实案例具有可见的标注状态和逐图对照，不伪造truth。
3. 最后交付US3与全量回归，证明新增定位不破坏既有模式。
4. 第一优先级004通过后，才建立下一增量处理4张槽壁亚像素失败。
