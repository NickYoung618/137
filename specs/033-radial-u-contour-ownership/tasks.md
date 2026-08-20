# Tasks: Position-Independent Radial U-Contour Ownership

**Input**: Design documents from `specs/033-radial-u-contour-ownership/`

**Tests**: Tests are mandatory and precede implementation.

## Phase 1: Setup and frozen evidence

- [X] T001 Record the 15 complete-visible and 67 mixed/occluded observed task IDs plus baseline commit/config/result hashes in `specs/033-radial-u-contour-ownership/quickstart.md`
- [X] T002 Verify no existing source, config or profile threshold changes are planned in `specs/033-radial-u-contour-ownership/plan.md`

## Phase 2: Foundational contracts

- [X] T003 [P] Add failing strict-config tests for default-off source adjudication v5 in `tests/test_slot_pose_contract.py`
- [X] T004 [P] Add failing profile-v8 compatibility and unchanged-threshold tests in `tests/test_single_shot_initial_profile.py`
- [X] T005 Define source adjudication v5 and portable profile v8 schemas in `contracts/slot-pose-config.schema.json` and `contracts/single-shot-initial-profile-v8.schema.json`

## Phase 3: User Story 1 - Prove the groove by its own physical shape (Priority: P1)

**Goal**: Verify a complete observed radial U-contour at any circular position without using fixture location.

**Independent Test**: Rotate synthetic valid and tangential counterexample contours around the circle; decisions remain correct and order-independent.

- [X] T006 [P] [US1] Add failing full-rotation, tangential-wall, one-wall, incomplete-floor, nonfinite and ordering tests in `tests/test_groove_shadow_geometry.py`
- [X] T007 [US1] Implement bounded radial U-contour ownership schema v4 in `algorithms/slot_pose/groove_shadow_geometry.py`
- [X] T008 [US1] Emit measured wall alignments, opening half-width, derived radial envelope and ordered checks in `algorithms/slot_pose/groove_shadow_geometry.py`

## Phase 4: User Story 2 - Separate lighting strength from source shape (Priority: P1)

**Goal**: Adjudicate only raw lighting imbalance after the complete physical contour is proven.

**Independent Test**: Photometric-only failures pass with verified radial ownership; every shape, coverage, endpoint or ownership corruption remains rejected.

- [X] T009 [P] [US2] Add failing v5 photometric-only and proof-corruption tests in `tests/test_source_consistency_adjudication.py`
- [X] T010 [US2] Implement immutable source adjudication v5 in `algorithms/slot_pose/source_consistency_adjudication.py`
- [X] T011 [US2] Pass complete bounded ownership evidence through `algorithms/slot_pose/legacy_adapter.py` without another image or refinement pass

## Phase 5: User Story 3 - Preserve safe rejection and auditability (Priority: P1)

**Goal**: Keep mixed, occluded, ambiguous and prior-version behavior fail-closed and explain every decision.

**Independent Test**: Synthetic safety cases and adapter integration retain null guidance, no PLC authority and deterministic diagnostics.

- [X] T012 [P] [US3] Add failing adapter tests for nested failed candidates, sole complete survivor, true ambiguity and safety nulls in `tests/test_single_real_groove.py`
- [X] T013 [P] [US3] Add diagnostic aggregation tests for ownership decisions in `tests/test_slot_pose_diagnostic_summary.py`
- [X] T014 [US3] Materialize portable profile v8 and audit report in `tools/prepare_single_shot_initial_config.py`
- [X] T015 [US3] Add ownership counters without private truth or paths in `tools/summarize_slot_pose_diagnostics.py`

## Phase 6: Validation and evidence

- [X] T016 Run focused tests, full available tests, root schema validation and diff checks; record commands and results in `specs/033-radial-u-contour-ownership/quickstart.md`
- [ ] T017 Replay the immutable 82 reviewed controls and full observed A2-700 set outside Git; record transitions, 15/15 recovery, 67/67 fail-closed, safety nulls and hashes in `/home/ubuntu/slot-pose-private-data/A2-700-observed-034-diagnostic-20260820/validation-report.json`
- [ ] T018 Run five-repeat determinism and uncontented reused-adapter warm P95 checks; record that no extra image load or full analysis pass occurs in `/home/ubuntu/slot-pose-private-data/A2-700-observed-034-diagnostic-20260820/performance-report.json`
- [ ] T019 Reconcile implementation against every FR/SC and append any real remaining work through SpecKit convergence in `specs/033-radial-u-contour-ownership/tasks.md`

## Dependencies and Execution Order

- Phase 1 freezes provenance before tests or code.
- Phase 2 contracts block runtime implementation.
- US1 physical proof blocks US2 adjudication and US3 integration.
- Validation begins only after all implementation and diagnostics tasks pass.

## Implementation Strategy

This feature is not accepted as a 15-image patch. The first executable slice is synthetic full-rotation radial U-contour proof plus tangential fixture counterexamples. Observed A2 replay is regression evidence only; physically separate new-part acceptance remains outside this implementation and is required before production or PLC claims.
