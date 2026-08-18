# Tasks: Sidewall Family Deduplication

**Input**: Design documents from `specs/031-sidewall-family-dedup/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required by FR-013; write boundary tests before implementation and retain observed/unseen data separation.

## Phase 1: Setup

**Purpose**: Freeze provenance and establish the explicit v2 contract.

- [x] T001 Record branch, base HEAD, corrected archive SHA, task IDs, image hashes and observed-data status in `specs/031-sidewall-family-dedup/quickstart.md`
- [x] T002 [P] Add strict v2 wall-family configuration cases and v1 compatibility expectations in `tests/test_slot_pose_contract.py`
- [x] T003 [P] Add the strict wall-source-family diagnostic schema skeleton in `contracts/groove-wall-source-family-diagnostic.schema.json`

---

## Phase 2: Foundational

**Purpose**: Define deterministic geometry evidence shared by recovery and safety stories.

- [x] T004 Add failing same-source, separated-parallel, crossing, short-overlap, nonfinite, transitive-bridge and ordering tests for `_select_wall_family` in `tests/test_groove_refinement.py`
- [x] T005 Implement strict v1/v2 schema-strategy pairing, finite ranges and bounded capacities in `algorithms/slot_pose/groove_refinement.py`
- [x] T006 Implement stable hypothesis canonicalization and bounded shared-longitudinal pair evidence without image resampling in `algorithms/slot_pose/groove_refinement.py`
- [x] T007 Implement deterministic complete-link physical-family grouping and observed representative ranking in `algorithms/slot_pose/groove_refinement.py`

**Checkpoint**: Synthetic geometry can distinguish one physical source from genuinely separate sources without changing existing uniqueness thresholds.

---

## Phase 3: User Story 1 - Recover a complete visible groove near fixtures (Priority: P1) 🎯 MVP

**Goal**: Stop counting near-coincident responses from one visible wall as multiple physical wall sources.

**Independent Test**: Reordered/duplicated/noisy hypotheses for one wall yield one family and identical observed representative geometry.

- [x] T008 [US1] Connect v2 grouping to the existing wall-family selection before the unchanged uniqueness gate in `algorithms/slot_pose/groove_refinement.py`
- [x] T009 [US1] Emit internal refinement diagnostic v4 with raw hypothesis count, membership, bounded pair evidence, family representatives and grouping timing in `algorithms/slot_pose/groove_refinement.py`
- [x] T010 [US1] Add a corrected `bad-0102` observed root-cause regression that asserts the start wall no longer fails solely from duplicate-family counting in `tests/test_single_real_groove.py`

**Checkpoint**: `bad-0102` may proceed to all unchanged downstream gates; no test requires it to become valid unless every independent physical gate passes.

---

## Phase 4: User Story 2 - Preserve fail-closed separation and occlusion behavior (Priority: P1)

**Goal**: Keep genuine ambiguity and upper-fixture mixed/occluded evidence non-authoritative.

**Independent Test**: Comparable separated families remain ambiguous and corrected `bad-0015` remains invalid with complete safety nulls.

- [x] T011 [P] [US2] Add adapter tests proving v1 and v2 recovery both require fixture/U-contour source exclusion in `tests/test_legacy_adapter.py`
- [x] T012 [P] [US2] Add corrected `bad-0015`, distinct-family and invalid-output safety regressions in `tests/test_single_real_groove.py`
- [x] T013 [US2] Replace exact v1 strategy-string safety detection with explicit versioned `wallFamilyRecoveryUsed` handling in `algorithms/slot_pose/legacy_adapter.py`
- [x] T014 [US2] Verify source-consistency, curved-floor, fixture exclusion, final quality and null-on-failure gates remain authoritative in `algorithms/slot_pose/legacy_adapter.py`

**Checkpoint**: Family grouping cannot bypass any existing physical/source/fixture/quality gate.

---

## Phase 5: User Story 3 - Produce reviewable and compatible evidence (Priority: P2)

**Goal**: Ship an auditable opt-in strategy and portable profile without changing prior configs.

**Independent Test**: Omitted/v1 configs retain prior behavior; v2 validates strictly and reports bounded versioned diagnostics.

- [x] T015 [P] [US3] Extend v2 configuration and diagnostic contracts in `contracts/slot-pose-config.schema.json` and `contracts/groove-wall-source-family-diagnostic.schema.json`
- [x] T016 [P] [US3] Add diagnostic aggregation fields and tests in `tools/summarize_slot_pose_diagnostics.py` and `tests/test_slot_pose_diagnostic_summary.py`
- [x] T017 [US3] Add contract dependency checks for explicit v2 usage in `algorithms/slot_pose/contract.py`
- [x] T018 [US3] Materialize a new portable single-shot profile version without mutating prior profiles in `tools/prepare_single_shot_initial_config.py`
- [x] T019 [US3] Add profile schema/audit and compatibility tests in `contracts/single-shot-initial-profile-v5.schema.json` and `tests/test_single_shot_initial_profile.py`
- [x] T020 [US3] Document v1/v2 selection, diagnostic meaning and non-production evidence limits in `config/README.md`

**Checkpoint**: Earlier portable profiles remain reproducible; v2 has a distinct effective identity and strict audit evidence.

---

## Phase 6: Validation and Polish

**Purpose**: Complete all required gates without converting observed data into acceptance truth.

- [x] T021 Run the focused unit/contract suite from `specs/031-sidewall-family-dedup/quickstart.md` and resolve every non-timing failure
- [x] T022 Run all root schema validations and `git diff --check`; record exact counts in a Git-external validation report
- [x] T023 Run corrected `bad-0102` and `bad-0015` five times with a reused adapter; record deterministic family membership, transitions, safety nulls and representative overlays in a Git-external report
- [x] T024 Run warm reused-adapter performance checks and confirm P95 is at most 2.5 seconds without repeated image loads or sampling passes; write `slot-pose-private-data/031-sidewall-family-dedup-validation/performance.json`
- [x] T025 Replay the available observed cohort only after code/config freeze; report failure-stage transitions and explicitly mark it non-acceptance data in `slot-pose-private-data/031-sidewall-family-dedup-validation/observed-regression.json`
- [x] T026 Record physically separate new-part acceptance as pending and prohibit accuracy/production/PLC claims in `specs/031-sidewall-family-dedup/quickstart.md`
- [x] T027 Run SpecKit convergence, final focused/full available tests, branch/HEAD/status audit and prepare `specs/031-sidewall-family-dedup/quickstart.md` handoff notes without merging main

---

## Dependencies & Execution Order

- Setup T001-T003 precedes foundational code.
- T004 must fail before T006-T008 implement the v2 behavior.
- T005-T007 block both P1 user stories.
- US1 T008-T010 and US2 T011-T014 share the grouping foundation; US2 safety integration must pass before profile materialization.
- US3 T015-T020 follows stable runtime diagnostics and safety semantics.
- Validation T021-T027 follows all desired stories and freezes code/config before observed replay.

## Parallel Opportunities

- T002 and T003 touch separate contract-test/schema files.
- T011 and T012 are separate adapter/real-case tests.
- T015 and T016 affect separate schema and summarizer surfaces.
- Documentation-only T020 can proceed after the runtime contract is stable.

## Implementation Strategy

The MVP is T001-T010: prove and integrate same-source grouping, then show that `bad-0102` no longer stops for duplicate physical-family counting. Safety completion T011-T014 is mandatory before any portable profile or broader replay. Compatibility and reporting T015-T020 precede final validation. Corrected cases and the 700 frames remain observed diagnostics throughout; physically separate acceptance remains a later external gate.

## Phase 7: Convergence

- [x] T028 Add crossing-line and transitive-bridge complete-link negative tests in `tests/test_groove_refinement.py` per FR-002/FR-005 (partial)
- [x] T029 Add adapter-level tests proving v2 wall recovery and v3 photometric adjudication cannot release pose without verified radial U-contour fixture exclusion in `tests/test_single_real_groove.py` per FR-012/FR-019 (partial)
- [x] T030 Emit selected physical source-family identity and bounded family-selection timing, then cover them in diagnostic schema/summary tests per FR-009 (partial)
- [x] T031 Freeze the corrected-case repeatability/performance report, record the unavailable physically separate acceptance gate, and preserve all invalid safety nulls per SC-004/SC-005/SC-006/SC-008 (partial)
