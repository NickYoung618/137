# Tasks: Fixture-Shadow Root-Cause Recovery

**Input**: Design documents from `specs/028-fixture-shadow-root-cause/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required by FR-014. Tests precede each implementation slice.

## Phase 1: Setup and frozen evidence

- [x] T001 Record branch, HEAD, clean-tree state, 140 manifest/config/result SHA-256 and seven physical groups in a Git-external 028 evidence directory
- [x] T002 Verify all 140 manifest image hashes and freeze the d776→027 transition ledger using tools/trace_groove_shadow_sources.py
- [x] T003 [P] Add 028 specification traceability references to specs/028-fixture-shadow-root-cause/research.md

---

## Phase 2: Foundational contracts

- [x] T004 [P] Add failing strict-config/default-off tests for versioned recognition recovery, wall-family refinement and source adjudication in tests/test_slot_pose_contract.py
- [x] T005 [P] Add failing diagnostic schema tests for original/effective decisions and four-state classification in tests/test_groove_shadow_discrimination.py
- [x] T006 Define strict nested config and diagnostic schema changes in contracts/slot-pose-config.schema.json, contracts/groove-shadow-source-diagnostic.schema.json and contracts/source-consistency-adjudication.schema.json
- [x] T007 Integrate strict default-off config loading and dependency validation in algorithms/slot_pose/contract.py

**Checkpoint**: Contracts reject unknown/nonfinite/unsafe configurations and omitted legacy configuration remains unchanged.

---

## Phase 3: User Story 1 - Recover complete visible grooves (Priority: P1)

**Goal**: Recover only candidates with unique downstream physical evidence while preserving all original gate results.

**Independent Test**: Synthetic width-only rejection, multi-peak wall contamination and contrast-only source rejection each recover only with unique complete evidence; structural failures do not recover.

- [x] T008 [P] [US1] Add failing provisional-recognition tests for exact width-only eligibility, multiple failures, order invariance and nonfinite evidence in tests/test_groove_recognition.py
- [x] T009 [P] [US1] Add failing multi-peak wall-family tests for unique family, zero family, multiple family, missing rows and deterministic order in tests/test_groove_refinement.py
- [x] T010 [P] [US1] Add failing source-adjudication v2 tests for exact contrast-only override and every structural-failure rejection in tests/test_source_consistency_adjudication.py
- [x] T011 [US1] Implement additive provisional candidate evidence without modifying original assessments in algorithms/slot_pose/groove_recognition.py
- [x] T012 [US1] Implement bounded single-sample-per-row tangential edge enumeration and deterministic wall-family selection in algorithms/slot_pose/groove_refinement.py
- [x] T013 [US1] Implement source-adjudication v2 using unchanged original non-contrast checks in algorithms/slot_pose/source_consistency_adjudication.py
- [x] T014 [US1] Route provisional and accepted candidates through one downstream refinement/resolution chain in algorithms/slot_pose/legacy_adapter.py
- [x] T015 [US1] Add runtime original/effective candidate, wall-family and source evidence propagation in algorithms/slot_pose/legacy_adapter.py

**Checkpoint**: No provisional candidate releases pose without unique two-wall geometry and effective source acceptance.

---

## Phase 4: User Story 2 - Reject shadow and occlusion safely (Priority: P1)

**Goal**: Correct semantic over-attribution and retain fail-closed behavior for structural mixing, missing walls and ambiguity.

**Independent Test**: Contrast-only asymmetry is not called occlusion; explicit structural/overlap failure remains mixed/occluded; multiple survivors remain ambiguous with null outputs.

- [x] T016 [P] [US2] Add failing classification tests for complete-visible, complete-near-shadow, mixed/occluded and indeterminate states in tests/test_groove_shadow_discrimination.py
- [x] T017 [P] [US2] Add failing end-to-end safety tests for provisional zero/multiple survivors and structural source failure in tests/test_single_real_groove.py
- [x] T018 [P] [US2] Add failing image/geometric evidence tests for stationary upper-small/lower-large circular fixture verification, lower-false-source versus upper-occlusion semantics, U-contour evidence, rotation, candidate-order, filename and fixed-angle independence in tests/test_groove_shadow_geometry.py
- [x] T019 [US2] Implement bounded per-frame fixture-body verification plus relative shadow-overlap, lower-false-source/upper-occlusion role separation, wall-continuity, curved groove-floor and endpoint-support evidence from the already loaded image in algorithms/slot_pose/groove_shadow_geometry.py
- [x] T020 [US2] Implement discriminator v2 effective-survivor rules in algorithms/slot_pose/groove_shadow_discrimination.py using explicit geometry evidence rather than contrast-only inference
- [x] T021 [US2] Propagate correct terminal stage/error code and preserve null pose/PLC fields in algorithms/slot_pose/legacy_adapter.py
- [x] T022 [US2] Update bounded review overlays and transition summaries in tools/render_slot_pose_review.py and tools/trace_groove_shadow_sources.py

**Checkpoint**: Classification no longer equates contrast asymmetry with occlusion and all non-authoritative paths remain null-safe.

---

## Phase 5: User Story 3 - Preserve circle and compatibility behavior (Priority: P2)

**Goal**: Explain circle failures, preserve 026 behavior and make no unsupported circle relaxation.

**Independent Test**: The two part-023 frames either pass unchanged final gates after a generic family-assignment improvement or remain explicit residual failures; six-image 026 default-off outputs remain identical.

- [x] T023 [P] [US3] Add regression assertions for broad-sector residual rejection and unchanged final circle gates in tests/test_physical_outer_circle.py
- [x] T024 [US3] Audit part-023 family/sector evidence and implement only a generic bounded assignment correction if unchanged gates prove it safe in algorithms/slot_pose/physical_outer_circle.py
- [x] T025 [US3] Run and record exact six-image 026 default-off compatibility comparison in a Git-external evidence directory

**Checkpoint**: No circle threshold or sector exclusion bound is relaxed.

---

## Phase 6: Polish and observed regression validation

- [x] T026 Run focused unit/contract tests and all root JSON Schema validation; record counts and hashes
- [ ] T027 Run the frozen 140-image replay once with reviewed 028 config and generate per-image overlays, transition ledger, stage/classification counts and seven-part grouping
- [ ] T028 Review every changed 140-image outcome and record complete-visible, complete-near-shadow, mixed/occluded or insufficient-evidence status without using folder class as truth
- [ ] T029 Verify all invalid/ambiguous pose, correction, direction and PLC fields are null and PLC authority is false
- [ ] T030 Run five-repeat same-adapter determinism and warm P95 performance checks on representative recovered and rejected frames
- [ ] T031 Run git diff checks, confirm branch/HEAD/worktree status, confirm no main merge, no PLC/HMI change and no sealed part-006 access
- [ ] T032 Update specs/028-fixture-shadow-root-cause/quickstart.md and produce the Git-external final observed-development report with explicit 700/new-part limitations

---

## Dependencies & Execution Order

- Phase 1 freezes evidence before any behavioral change.
- Phase 2 blocks implementation.
- US1 establishes effective candidates; US2 consumes them and follows US1.
- US3 is independent after Phase 2 but must finish before the final replay.
- Phase 6 follows all selected user stories.

## Parallel Opportunities

- T004 and T005 touch different test files.
- T008, T009 and T010 are independent failing-test slices.
- T016 and T017 are independent classification/integration tests.
- T021 can proceed while US1/US2 implementation is underway.

## Implementation Strategy

1. Freeze evidence and contracts.
2. Deliver provisional recognition plus unique wall/source proof as the MVP.
3. Correct semantic classification and safety propagation.
4. Keep unsupported circle failures explicit.
5. Replay and visually audit all 140 observed frames; do not claim production accuracy.
