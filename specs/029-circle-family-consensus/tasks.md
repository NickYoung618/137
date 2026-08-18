# Tasks: Circle-Family Consensus Stabilization

**Input**: Design documents from `specs/029-circle-family-consensus/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/family-consensus.md`

**Tests**: Required by FR-012 through FR-014.

## Phase 1: Setup and frozen evidence

- [x] T001 Record the frozen 442/449 hashes, current v1 outputs, unchanged thresholds and approved 140-manifest boundaries in Git-external 029 evidence
- [x] T002 [P] Add representative-bias and version-1 compatibility test fixtures in `tests/test_physical_outer_circle.py`
- [x] T003 [P] Add version-2 config and diagnostic contract expectations in `tests/test_slot_pose_contract.py`

## Phase 2: User Story 1 - Stable family consensus (Priority: P1)

**Goal**: Consolidate one grouped family from all member evidence and accept normal outer circles under unchanged gates.

**Independent Test**: Synthetic representative-bias fixture plus frozen 442/449 both pass with one family and unchanged thresholds.

- [x] T004 [US1] Add failing tests for deterministic member consensus, stable reassignment and observed-points-only output in `tests/test_physical_outer_circle.py`
- [x] T005 [US1] Implement bounded version-2 intra-family consensus and reassignment in `algorithms/slot_pose/physical_outer_circle.py`
- [x] T006 [US1] Emit bounded per-family consensus diagnostics in `algorithms/slot_pose/physical_outer_circle.py`
- [x] T007 [US1] Replay frozen frames 442 and 449 with a Git-external version-2 config and verify every original final circle threshold remains unchanged

## Phase 3: User Story 2 - Ambiguity and safe failure (Priority: P1)

**Goal**: Ensure consensus never averages distinct families or releases unstable evidence.

**Independent Test**: Multiple-family, non-convergent, insufficient and nonfinite cases fail explicitly and root invalid outputs remain null.

- [x] T008 [US2] Add failing multiple-family, candidate-order, rotation, non-convergence and nonfinite tests in `tests/test_physical_outer_circle.py`
- [x] T009 [US2] Enforce convergence, finite evidence and unchanged zero/multiple-family outcomes in `algorithms/slot_pose/physical_outer_circle.py`
- [x] T010 [US2] Verify full-frame ambiguity propagation and single-load behavior in `tests/test_full_frame_circle_locator.py` and `tests/test_single_real_groove.py`

## Phase 4: User Story 3 - Versioned compatibility (Priority: P2)

**Goal**: Preserve v1 while exposing a strictly validated and auditable v2 strategy.

**Independent Test**: Existing v1 tests/evidence remain equivalent; v2 config/schema/diagnostics validate.

- [x] T011 [US3] Accept and strictly validate the v2 strategy in `algorithms/slot_pose/physical_outer_circle.py`, `algorithms/slot_pose/contract.py` and `contracts/slot-pose-config.schema.json`
- [x] T012 [US3] Extend the additive diagnostic schema in `contracts/physical-circle-edge-family-diagnostic.schema.json`
- [x] T013 [US3] Materialize and audit v2 in `tools/prepare_single_shot_initial_config.py` and `contracts/single-shot-initial-profile-v4.schema.json` without mutating v1 identity
- [x] T014 [US3] Verify trace/runtime parity and order/rotation invariance in `tools/trace_circle_edge_families.py` and `tests/test_circle_edge_family_trace.py`

## Phase 5: Regression, performance and handoff

- [x] T015 Run focused unit and contract tests plus all root JSON Schemas
- [x] T016 Replay the frozen 140 observed images once, verify 442/449 recovery and all 41 reviewed mixed/occluded cases remain fail-closed, and record per-stage counts outside Git
- [x] T017 Run five static repeats and warm reused-adapter performance for recovered and rejected representatives, enforcing exact determinism and P95 no greater than 2.5 seconds
- [x] T018 Run six-image 026 v1 compatibility comparison and confirm legacy effective identity/output equivalence
- [x] T019 Update `specs/029-circle-family-consensus/quickstart.md`, mark completed tasks, run convergence analysis and record the final observed-development limitations
- [ ] T020 Commit and push the reviewed branch only after `git diff --check`, tests, schemas, evidence hashes and clean-worktree verification, then prepare the Mac 700-image diagnostic prompt

## Dependencies & Execution Order

- Phase 1 freezes evidence and writes tests before implementation.
- US1 establishes consensus; US2 hardens its failure boundaries; US3 versions integration.
- Regression and handoff require all three stories.
- No task authorizes main merge, PLC/HMI work, sealed part-006 access or production claims.

## Implementation Strategy

Implement the smallest versioned change inside the existing selector, prove the two false rejects without threshold changes, then expand validation outward to safety regressions, compatibility, performance and Mac handoff.
