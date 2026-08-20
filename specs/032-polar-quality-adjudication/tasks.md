# Tasks: Physical-Groove Polar Quality Adjudication

**Input**: Design documents from `/specs/032-polar-quality-adjudication/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/polar-quality-adjudication.md`

**Tests**: Required by FR-016 and SC-009. Tests are written and observed failing before their corresponding implementation.

## Phase 1: Setup (Shared Evidence and Contract Skeleton)

**Purpose**: Freeze the observed root cause and establish additive contract locations without changing runtime behavior.

- [X] T001 Record the immutable A2-700 observed evidence hashes, original 700 performance failure and no-production-claim boundary in `specs/032-polar-quality-adjudication/quickstart.md`
- [X] T002 [P] Add the nested default-off configuration contract test skeleton in `tests/test_slot_pose_contract.py`
- [X] T003 [P] Add the versioned diagnostic schema skeleton in `contracts/polar-quality-adjudication-diagnostic.schema.json`

---

## Phase 2: Foundational (Pure Decision Core)

**Purpose**: Build a deterministic, image-free and fail-closed evidence decision before adapter integration.

**⚠️ CRITICAL**: User story integration cannot begin until the pure decision and strict configuration rules pass.

- [X] T004 Write failing unit tests for sole-polar acceptance, threshold equality, disabled/not-needed states, reordered inputs and immutable original failures in `tests/test_polar_quality_adjudication.py`
- [X] T005 Write failing unit tests that remove or corrupt every required physical proof, add a second failure/candidate and inject nonfinite values in `tests/test_polar_quality_adjudication.py`
- [X] T006 Implement strict schema-version/strategy/default-off configuration parsing in `algorithms/slot_pose/polar_quality_adjudication.py`
- [X] T007 Implement ordered physical-proof validation and deterministic original/effective quality decision in `algorithms/slot_pose/polar_quality_adjudication.py`

**Checkpoint**: The pure decision can only remove a sole `polar_score` failure and denies every incomplete or ambiguous evidence bundle.

---

## Phase 3: User Story 1 - Release a Complete Independently Proven Groove (Priority: P1) 🎯 MVP

**Goal**: Allow a complete unique physical groove to proceed when the unchanged legacy polar score is its only failed quality check.

**Independent Test**: A representative single-groove fixture with every physical proof accepted becomes valid through the versioned decision, while its original polar failure, score and threshold remain unchanged.

### Tests for User Story 1

- [X] T008 [US1] Add a failing adapter test for sole-polar release, immutable original diagnostics and refined-groove-only pose in `tests/test_single_real_groove.py`
- [X] T009 [US1] Add a failing adapter test proving classifier terminal status and final validity use effective failures without mutating the original list in `tests/test_legacy_adapter.py`

### Implementation for User Story 1

- [X] T010 [US1] Build the bounded adjudication evidence bundle after accepted single-groove pose construction in `algorithms/slot_pose/legacy_adapter.py`
- [X] T011 [US1] Add separate effective failures and route shadow classification/final rejection through them in `algorithms/slot_pose/legacy_adapter.py`
- [X] T012 [US1] Emit versioned original/effective adjudication diagnostics without changing confidence or polar rotation in `algorithms/slot_pose/legacy_adapter.py`
- [X] T013 [US1] Record an observed representative regression proving bad-0041 advances only through adjudication in Git-external `A2-700-observed-032-20260820/root-case/result-bad-0041.json`

**Checkpoint**: The complete-groove sole-polar case is valid, deterministic and fully auditable without any threshold change.

---

## Phase 4: User Story 2 - Keep Uncertain, Mixed and Occluded Grooves Rejected (Priority: P1)

**Goal**: Ensure the exception cannot release ambiguous, incomplete, fixture-mixed, occluded or multiply failing evidence.

**Independent Test**: Each proof is removed independently and mixed/occluded fixtures are replayed; every result remains invalid with complete null safety.

### Tests for User Story 2

- [X] T014 [US2] Add adapter fail-closed tests for mixed/occluded classification, candidate ambiguity, nonfinite endpoints and missing floor/source/fixture proof in `tests/test_single_real_groove.py`
- [X] T015 [US2] Add null angle/correction/direction/mechanical/PLC and non-authoritative PLC assertions for denied integration paths in `tests/test_single_real_groove.py`

### Implementation for User Story 2

- [X] T016 [US2] Enforce every physical proof dependency and explicit ordered denial reason in `algorithms/slot_pose/polar_quality_adjudication.py`
- [X] T017 [US2] Preserve mixed/occluded and every non-polar terminal failure as authoritative in `algorithms/slot_pose/legacy_adapter.py`

**Checkpoint**: All unsafe or incomplete cases remain fail-closed and cannot emit guidance or commands.

---

## Phase 5: User Story 3 - Preserve Compatibility and Auditability (Priority: P2)

**Goal**: Keep old configurations unchanged and make enabled decisions strictly versioned, schema-valid and reportable.

**Independent Test**: Omitted and disabled configurations reproduce legacy decisions; enabled diagnostics validate and report original and effective states separately.

### Tests for User Story 3

- [X] T018 [P] [US3] Add strict nested configuration, dependency and compatibility tests in `tests/test_slot_pose_contract.py`
- [X] T019 [P] [US3] Add diagnostic summary aggregation tests for accepted/denied/not-needed decisions in `tests/test_slot_pose_diagnostic_summary.py`
- [X] T020 [P] [US3] Add portable profile version and audit-block tests in `tests/test_single_shot_initial_profile.py`

### Implementation for User Story 3

- [X] T021 [US3] Validate the nested runtime configuration and prohibited mode/source combinations in `algorithms/slot_pose/contract.py`
- [X] T022 [US3] Extend the root configuration schema with the strict default-off object in `contracts/slot-pose-config.schema.json`
- [X] T023 [US3] Complete the closed versioned diagnostic schema in `contracts/polar-quality-adjudication-diagnostic.schema.json`
- [X] T024 [US3] Aggregate adjudication statuses, reasons and original/effective failures in `tools/summarize_slot_pose_diagnostics.py`
- [X] T025 [US3] Materialize a new portable single-shot profile version and audit block without mutating prior profiles in `tools/prepare_single_shot_initial_config.py`
- [X] T026 [US3] Document configuration, compatibility and non-authoritative rollout in `config/README.md` and `specs/032-polar-quality-adjudication/quickstart.md`

**Checkpoint**: Old configs remain compatible; the enabled path is strictly configured, schema-valid and auditable.

---

## Phase 6: Validation and Handoff

**Purpose**: Verify determinism, safety, observed regression behavior and performance without converting observed A2 data into acceptance truth.

- [X] T027 Run focused adjudication/adapter/contract/profile/summary tests and all root-schema validation; record exact commands and counts in `specs/032-polar-quality-adjudication/quickstart.md`
- [X] T028 Run five static repeats for one released and one denied representative and verify identical non-timing diagnostics and pose/null outputs in Git-external evidence
- [X] T029 Replay the frozen observed A2-700 set and verify the 20 sole-polar cases advance only by adjudication, the 24 recovered-valid remain valid, the 174 mixed/occluded remain invalid, and all invalid safety fields remain null
- [X] T030 Measure same-adapter preloaded warm P95 and confirm no second decode, polar sampling, circle search, recognition or refinement pass in Git-external performance evidence
- [X] T031 Run the full available test suite, `git diff --check`, schema checks and SpecKit convergence; record branch, commit candidate and clean/dirty status in `specs/032-polar-quality-adjudication/quickstart.md`
- [X] T032 Document physically separate new-part validation as an outstanding external acceptance gate and prohibit accuracy/production/PLC claims until it passes in `specs/032-polar-quality-adjudication/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** establishes evidence and contract skeletons.
- **Phase 2** depends on Phase 1 and blocks all runtime integration.
- **User Story 1** depends on the pure decision core.
- **User Story 2** depends on User Story 1 integration and hardens it fail-closed.
- **User Story 3** depends on the stable runtime diagnostic shape from User Stories 1 and 2.
- **Validation** depends on all implementation stories.

### Within Each User Story

- Write and run the listed tests first; observe the expected failure before implementation.
- Preserve the original quality evidence before creating effective failures.
- Complete safety tests before enabling any observed replay profile.
- Do not mark A2 observed replay as unseen acceptance or production evidence.

### Parallel Opportunities

- T002 and T003 touch independent contract files.
- T018, T019 and T020 touch independent test files after the runtime diagnostic shape is stable.
- No runtime-edit tasks are marked parallel because they share adapter and decision semantics.

## Implementation Strategy

1. Implement the pure, constant-size decision with exhaustive fail-closed tests.
2. Integrate it default-off and prove legacy compatibility.
3. Prove the sole-polar complete-groove path and every denial/null-safety path.
4. Add schema, profile and reporting support.
5. Run observed regression and performance evidence separately from new-part acceptance.

## Notes

- The 700 A2 frames are observed diagnostic data only.
- The polar threshold remains 3.0; no recognition, refinement, source, ambiguity, fixture or outer-circle threshold may be relaxed.
- No filename, capture index, fixed-angle whitelist, directory class, human label or CODEX review enters runtime logic.
- Do not read sealed part-006, modify PLC/HMI or merge main.
