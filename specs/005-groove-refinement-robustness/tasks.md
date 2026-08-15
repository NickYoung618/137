# Tasks: 槽壁亚像素精修稳定性

**Input**: Design documents from `specs/005-groove-refinement-robustness/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: 本功能依Constitution和用户要求采用TDD，先运行失败测试再实现。

## Phase 1: Setup and Baseline

- [x] T001 Record the clean `5e3a5ce` baseline, 114-test result, 25/25 circle and groove recognition, 22/25 refinement and three `startSide_line_residual` failures in `specs/005-groove-refinement-robustness/evidence/baseline-summary.json`
- [x] T002 Record read-only point-consensus diagnosis for frames 23-25, including old/new residual, support ratio, span and no-truth limitation in `specs/005-groove-refinement-robustness/evidence/diagnosis-summary.json`

## Phase 2: Foundational Contracts

- [x] T003 [P] Add failing strict configuration tests for v1/v2 strategy selection and all finite consensus thresholds in `tests/test_slot_pose_contract.py`
- [x] T004 [P] Add failing diagnostic contract tests for v2 point/inlier/rejected/model-margin fields and null-on-failure behavior in `tests/test_groove_refinement.py`
- [x] T005 Implement backward-compatible v1/v2 configuration validation in `algorithms/slot_pose/groove_refinement.py`, `algorithms/slot_pose/contract.py` and `contracts/slot-pose-config.schema.json`

## Phase 3: User Story 1 - 唯一恢复真实槽壁 (Priority: P1) MVP

**Independent Test**: 可控直槽壁在圆角/离群干扰下恢复，短边、双线和单侧失败仍安全关闭。

- [x] T006 [P] [US1] Add failing deterministic-consensus tests for entrance/bottom fillets and isolated outliers in `tests/test_groove_refinement.py`
- [x] T007 [P] [US1] Add failing negative tests for short support, low inlier ratio, two-line ambiguity and invalid intersection in `tests/test_groove_refinement.py`
- [x] T008 [P] [US1] Add failing wraparound and repeat-run determinism tests for v2 in `tests/test_groove_refinement.py`
- [x] T009 [US1] Implement bounded deterministic pair hypotheses, iterative TLS inlier refinement and stable ranking in `algorithms/slot_pose/groove_refinement.py`
- [x] T010 [US1] Implement projection-span, inlier-ratio, residual and coarse-intersection gates in `algorithms/slot_pose/groove_refinement.py`
- [x] T011 [US1] Implement intersection-angle model deduplication, best/second support margin and explicit ambiguity failure in `algorithms/slot_pose/groove_refinement.py`
- [x] T012 [US1] Integrate v2 side decisions into two-side opening output without coarse-angle fallback in `algorithms/slot_pose/groove_refinement.py` and `algorithms/slot_pose/legacy_adapter.py`

## Phase 4: User Story 2 - 可解释精修审阅 (Priority: P2)

**Independent Test**: 审阅图和表格可逐点区分全部检测点、内点、拒绝点和最终交点。

- [x] T013 [P] [US2] Add failing review tests for detected/inlier/rejected point counts, fixed colors and side-model CSV fields in `tests/test_slot_pose_review.py`
- [x] T014 [P] [US2] Add failing summary tests for v1/v2 refinement counts, failure reasons, model margins and paired circular angle deltas in `tests/test_slot_pose_diagnostic_summary.py`
- [x] T015 [US2] Render detected/inlier/rejected sidewall points, final lines and intersections with a fixed legend in `tools/render_slot_pose_review.py`
- [x] T016 [US2] Export per-side consensus evidence and v1/v2 paired refinement statistics in `tools/render_slot_pose_review.py` and `tools/summarize_slot_pose_diagnostics.py`

## Phase 5: User Story 3 - 兼容和安全回归 (Priority: P3)

**Independent Test**: v1结果可复现，v2不改变上游圆/槽选择，任一精修失败仍保持空正式角。

- [x] T017 [P] [US3] Add v1 exact-compatibility and v2 fail-closed integration tests in `tests/test_single_real_groove.py`
- [x] T018 [P] [US3] Update example configuration and documentation without changing the v2 top-level result contract in `config/inspection.example.json`, `config/README.md` and `README.md`
- [x] T019 [US3] Run legacy 72-angle, paired positive/negative, 004 locator and manual-BMP development comparisons and record de-identified evidence in `specs/005-groove-refinement-robustness/evidence/compatibility-summary.json`

## Phase 6: Real-data Validation and Polish

- [x] T020 Run external v1/v2 paired batches on the same 25-image manifest and generate overlays, CSV, JSON and contact sheets outside Git
- [x] T021 Record 22-frame v1/v2 circular deltas, three recovered-frame quality/consistency, upstream candidate invariance and failure distribution in `specs/005-groove-refinement-robustness/evidence/real-data-summary.json`
- [x] T022 Measure refinement overhead, full-image P50/P95/max, batch throughput and peak RSS in `specs/005-groove-refinement-robustness/evidence/performance-summary.json`
- [x] T023 Confirm annotation coverage and static repeatability remain `NOT_EVALUATED` without reviewed same-image truth/grouping in `specs/005-groove-refinement-robustness/evidence/annotation-status.json`
- [x] T024 Run full unittest, explicit Schema, CLI, JSON, `git diff --check`, media/large-file/private-path pollution and protected-workspace read-only checks, then complete `specs/005-groove-refinement-robustness/tasks.md`
- [x] T025 Run final read-only Spec Kit analysis and create a local commit on `003-a2-paired-notch-stability` without push or merge

## Dependencies & Execution Order

- Phase 1 -> Phase 2 -> US1 -> US2 -> US3 -> Phase 6.
- T003/T004可并行设计，T005统一契约。
- T006～T008先失败，T009～T012按候选、质量门、唯一性、集成顺序实现。
- US2依赖US1的v2诊断；US3依赖US1稳定。
- 真实精度和正式静态重复性不因T020通过而解锁，仍依赖人工标注和采集分组。

## Implementation Strategy

1. 先完成US1的确定性共识和负样本fail-closed。
2. 再交付US2的逐点审阅，不用通过率替代视觉证据。
3. 最后运行v1/v2成对真实数据和所有兼容/资源门。
