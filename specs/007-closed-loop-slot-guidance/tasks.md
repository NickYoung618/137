# Tasks: 单真槽闭环旋转引导

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`

**Tests**: 本功能明确要求TDD、Schema、历史回归和25图外置实跑。

## Phase 1: Setup and version boundary

- [x] T001 Confirm the clean feature-branch baseline and record current full-test count in `specs/007-closed-loop-slot-guidance/tasks.md`
- [x] T002 Define the v3 configuration boundary in `contracts/slot-pose-config.schema.json` without changing v1/v2 behavior
- [x] T003 [P] Add the pose diagnostic contract in `contracts/single-real-groove-pose-v3.schema.json`
- [x] T004 [P] Add the top-level result contract in `contracts/slot-pose-result-v3.schema.json`

## Phase 2: Foundational guidance model

**Purpose**: Establish the versioned state and math used by all stories.

- [x] T005 Write failing authoritative-example, deadband, wrap, quadrant, and unavailable-state tests in `tests/test_closed_loop_guidance.py`
- [x] T006 Implement the pure v3 image-frame guidance state machine in `algorithms/slot_pose/single_groove_pose.py`
- [x] T007 Extend v3 pose construction and stable detection-failure guidance in `algorithms/slot_pose/single_groove_pose.py`
- [x] T008 Validate the v3 pose diagnostic against `contracts/single-real-groove-pose-v3.schema.json` in `tests/test_closed_loop_guidance.py`

**Checkpoint**: Pure current-angle-to-guidance behavior satisfies the three authoritative examples.

## Phase 3: User Story 1 - Reliable shortest rotation guidance (Priority: P1)

**Goal**: Reliable geometry at any current pose emits a valid shortest signed image-frame correction.

**Independent Test**: Run `tests.test_closed_loop_guidance` with the three authoritative examples and the inclusive 80°–90° deadband.

- [x] T009 [US1] Write failing v3 adapter integration tests for accepted geometry and 0/1/multiple groove outcomes in `tests/test_single_real_groove.py`
- [x] T010 [US1] Enable existing subpixel refinement for v3 in `algorithms/slot_pose/legacy_adapter.py`
- [x] T011 [US1] Ensure v3 role/pose output consumes exactly one accepted groove without changing v1/v2 paths in `algorithms/slot_pose/legacy_adapter.py`
- [x] T012 [US1] Add single-image CLI regression tests for adjustment, deadband, and detection failure in `tests/test_slot_pose_cli.py`

**Checkpoint**: One accepted groove plus trusted subpixel opening yields DETECTED regardless of current quadrant.

## Phase 4: User Story 2 - Separate detection, guidance, and PLC authority (Priority: P1)

**Goal**: Top-level valid means reliable image guidance, while actuator output remains independently blocked.

**Independent Test**: Validate successful/failed result v3 fixtures and prove old configurations still emit result v2.

- [x] T013 [US2] Write failing v3 result and PLC-gate contract tests in `tests/test_slot_pose_contract.py`
- [x] T014 [US2] Implement version-aware result building and validation in `algorithms/slot_pose/contract.py`
- [x] T015 [US2] Route v3 image guidance without calling the legacy mechanical-angle gate in `algorithms/slot_pose/main.py`
- [x] T016 [US2] Keep `mechanicalCorrectionDeg` and `plcCommand` null with an explicit mapping blocker in `algorithms/slot_pose/contract.py`
- [x] T017 [US2] Validate v3 success/failure payloads against `contracts/slot-pose-result-v3.schema.json` in `tests/test_slot_pose_contract.py`
- [x] T018 [US2] Prove legacy, paired, multi-role, and single v1/v2 compatibility in the existing full test suite

**Checkpoint**: A reliable image result is valid even when PLC execution is blocked.

## Phase 5: User Story 3 - Human-reviewable guidance evidence (Priority: P2)

**Goal**: Review artifacts display detection and adjustment state without misleading PASS/FAIL labels.

**Independent Test**: Build a synthetic review set containing in-position, clockwise, counterclockwise, and detection-failed records.

- [x] T019 [US3] Write failing review JSON/CSV/overlay wording tests in `tests/test_slot_pose_review.py`
- [x] T020 [US3] Add guidance-aware review parsing, overlay text, `guidance.csv`, and detection-only `failures.csv` in `tools/render_slot_pose_review.py`
- [x] T021 [US3] Add detection/guidance/direction/PLC summary counts in `tools/summarize_slot_pose_diagnostics.py`
- [x] T022 [US3] Version the reference-anchored diagnostics index contract in `contracts/reference-anchored-diagnostics.schema.json`
- [x] T023 [US3] Export v3 guidance and retain AUTO LabelMe non-truth provenance in `tools/export_reference_anchored_diagnostics.py`
- [x] T024 [US3] Update reference export and Schema tests in `tests/test_reference_anchored_diagnostics.py`

**Checkpoint**: NEEDS_ADJUSTMENT is visually a successful detection and only DETECTION_FAILED enters the failure index.

## Phase 6: User Story 4 - Stateless recapture loop safety (Priority: P2)

**Goal**: Each frame independently emits adjustment, zero, or unavailable without reusing prior state.

**Independent Test**: Run the sequence adjustment → in-position → failed and assert no prior value leaks.

- [x] T025 [US4] Add a three-frame statelessness and stale-value non-reuse test in `tests/test_closed_loop_guidance.py`
- [x] T026 [US4] Add batch ordering/task identity regression coverage in `tests/test_slot_pose_batch.py`
- [x] T027 [US4] Document the caller-side closed-loop stop/recapture/failure transition in `README.md`

## Phase 7: Real-data replay and evidence

- [x] T028 Create a Git-safe v3 example configuration in `configs/` with no private path or PLC command mapping
- [x] T029 Run the external 25-JPEG batch and export 25 overlays, 25 AUTO LabelMe files, CSV, review JSON, failures index, and contact sheet outside Git
- [x] T030 Compare real-run counts to SC-006 and record only de-identified aggregate evidence in the 007 spec directory
- [x] T031 Measure cold/steady P50/P95/max, serial wall-clock throughput, and peak RSS on the stated server
- [x] T032 Report accuracy and static repeatability as `NOT_EVALUATED` because the 25 images lack per-image truth and confirmed repeat groups

## Phase 8: Documentation, analysis, and release gates

- [x] T033 Update `README.md` and `specs/007-closed-loop-slot-guidance/quickstart.md` with v3 semantics, commands, safety boundary, and evidence limitations
- [x] T034 Run the full test suite, explicit JSON Schema validation, `git diff --check`, JSON parsing, large-file/media checks, and private absolute-path scan
- [x] T035 Run Spec Kit consistency analysis, resolve all critical/high findings, and record final verification evidence
- [x] T036 Commit the completed 007 feature locally on the feature branch without push or merge

## Dependencies and execution order

- Phase 1 establishes the explicit v3 boundary.
- Phase 2 blocks all user stories.
- US1 and US2 form the executable MVP and must finish before review exports.
- US3 consumes the v3 runtime result but does not change detection math.
- US4 verifies stateless safety after runtime integration.
- Real-data replay follows all code and review changes.
- Final gates and the local commit follow evidence capture.

## Implementation strategy

1. Write and observe failing tests for each behavior before implementation.
2. Reuse the existing physical-circle, real-groove, and subpixel refinement path; add only the versioned state and integration needed by the spec.
3. Keep external media and generated review artifacts outside Git; commit only de-identified aggregate evidence.
4. Do not push, merge main, write PLC, or change the upper-computer integration.

## Verification record

- Clean code baseline before implementation: 124 tests passed, 5 skipped.
- Final full suite with explicit JSON Schema dependency: 142 tests passed, 0 skipped.
- Spec Kit post-implementation analysis: 0 critical, 0 high, 0 medium consistency findings; no remaining clarification markers.
- Convergence audit: all FR-001 through FR-024 and SC-001 through SC-011 have implementation/test/evidence coverage; no additional implementation task was appended.
- External real replay and its hashes/performance are recorded in `evidence/real-25-summary.json`; media remains outside Git.
