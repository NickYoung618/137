# Tasks: Main Housing Registration for A2 Short Lines

**Input**: Design documents in `specs/007-main-housing-registration/`  
**Tests**: Required by the feature specification and constitution

## Phase 1 — Setup and immutable evidence

- [x] T001 Record the old-transform root cause; the later-invalidated endpoint evidence is withdrawn by feature 008.
- [x] T002 Confirm clean starting worktree and immutable `algorithms/end_face/core.py` SHA-256.
- [x] T003 Create v2 diagnostic contract in `specs/007-main-housing-registration/contracts/`.

## Phase 2 — User Story 1: main housing instance selection (P1)

**Independent test**: multi-instance synthetic target selects the main housing independently of legacy geometry; ambiguous/no-support targets fail closed.

- [x] T004 [US1] Add failing component enumeration, distractor selection, ambiguity, and no-support tests in `tests/test_main_housing_registration.py`.
- [x] T005 [US1] Implement housing hypotheses and robust circle refinement in `algorithms/end_face/main_housing_registration.py`.
- [x] T006 [US1] Implement reference instance selection; feature 008 replaces endpoint-annulus membership with image-only circle dominance.

## Phase 3 — User Story 2: center/scale/angle registration and local search (P1)

**Independent test**: known synthetic similarity transforms recover center, scale and angle with no measurement-annotation input.

- [x] T007 [US2] Extend failing tests for synthetic transform recovery and rotation ambiguity; feature 008 removes the invalid external endpoint test.
- [x] T008 [US2] Implement annular rotation correlation, transform gates, and serializable registration diagnostics.
- [x] T009 [US2] Add strict `config/end_face_short_line_candidate.v2.json` validation without weakening v1 thresholds.
- [x] T010 [US2] Project external 19/30 lines and wire v2 registration into `algorithms/end_face/short_line_candidate.py` before bounded local refinement.

## Phase 4 — User Story 3: independent results and contracts (P1)

**Independent test**: candidate evaluation leaves legacy measurements/quality identical and emits v2 `candidateValid` plus all four transition values under schema.

- [x] T011 [US3] Add regression tests for legacy immutability, missing-reference fail-closed behavior, v1 compatibility, and transition semantics.
- [x] T012 [US3] Add v2 provenance/registration diagnostics to candidate output while preserving old core records.
- [x] T013 [US3] Update `contracts/a-end-face-result.schema.json` and schema tests for both versioned candidate IDs.

## Phase 5 — User Story 4: external Mac batch evaluation (P2)

**Independent test**: server synthetic manifest exercises the same compare path and the documented Mac command keeps outputs external.

- [x] T014 [US4] Verify compare/batch tools accept v2 config plus external LabelMe and aggregate independent transitions.
- [x] T015 [US4] Document registration-only Mac commands and defer 25-frame candidate acceptance pending corrected truth.

## Phase 6 — Verification and audit

- [x] T016 Run targeted registration, candidate, LabelMe, CLI, batch, and schema tests.
- [x] T017 Run the full Python unittest suite with no failures.
- [x] T018 Execute the read-only SpecKit analyze traceability review and record its gate result in the implementation handoff.
- [x] T019 Verify core SHA-256 and audit tracked files for raw images, JSONL, archives, and large files.
- [x] T020 Mark tasks complete only after all gates pass; review `git diff` for scope and user-change preservation.

## Dependencies

- T004 precedes T005-T006; T007 precedes T008-T010.
- T010 depends on T006, T008, and T009.
- T011 precedes T012-T013.
- T014 depends on T010 and T012.
- T016-T020 depend on all implementation tasks.
