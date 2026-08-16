# Tasks: Revoke Invalid A2 Short-Line Anchor

**Input**: Design documents in `specs/008-revoke-invalid-anchor/`
**Tests**: Required by the feature specification and constitution

## Phase 1 — Setup and decontamination inventory

- [x] T001 Record the fingerprint revocation and forbidden uses in `specs/008-revoke-invalid-anchor/spec.md` and `research.md`.
- [x] T002 Confirm the starting worktree and immutable core SHA in the implementation log.
- [x] T003 Inventory and retract revoked-anchor claims in `specs/007-main-housing-registration/`, `README.md`, and tests.

## Phase 2 — User Story 1: shared revoked-reference rejection (P1)

**Independent test**: a synthetic reference with a mocked revoked fingerprint fails through the shared loader before parsing/template use; another synthetic reference still passes.

- [x] T004 [US1] Add red revocation tests in `tests/test_short_line_labelme_reference.py`.
- [x] T005 [US1] Implement the path-independent revoked-fingerprint gate in `algorithms/end_face/short_line_candidate.py`.
- [x] T006 [US1] Verify single CLI, batch, compare, and inspect entry points all use the shared loader without bypasses.

## Phase 3 — User Story 2: annotation-independent main-housing registration (P1)

**Independent test**: construct and run the registrar with image/config only; recover synthetic translation/scale/rotation and reject ambiguous reference instances.

- [x] T007 [US2] Rewrite registrar tests to prohibit any 19/30 input in `tests/test_main_housing_registration.py`.
- [x] T008 [US2] Replace annotation-annulus reference selection with supported-circle dominance in `algorithms/end_face/main_housing_registration.py`.
- [x] T009 [US2] Replace anchor-radius config fields with reference-dominance gates in `config/end_face_short_line_candidate.v2.json` and its schema.
- [x] T010 [US2] Update `algorithms/end_face/short_line_candidate.py` to construct the annotation-independent registrar while deferring endpoint projection to a non-revoked reference.

## Phase 4 — User Story 3: registration-only diagnostics (P1)

**Independent test**: synthetic single and manifest batch runs emit strict image-free JSON/JSONL with no candidate/recovery fields.

- [x] T011 [US3] Add red single/batch diagnostic tests in `tests/test_registration_diagnostic.py`.
- [x] T012 [US3] Implement `tools/diagnose_main_housing_registration.py` with strict single and batch output.
- [x] T013 [US3] Add strict diagnostic and batch-summary schemas, including immutable core provenance, and schema tests.

## Phase 5 — User Story 4: corrected-truth handoff (P2)

**Independent test**: documentation contains registration-only Mac commands and a corrected-reference placeholder, with no runnable revoked-reference acceptance command.

- [x] T014 [US4] Correct historical 007 evidence and remove its external self-anchor test/claim.
- [x] T015 [US4] Update `README.md` and `specs/008-revoke-invalid-anchor/quickstart.md` with registration-only and deferred corrected-reference commands.

## Phase 6 — Verification

- [x] T016 Run targeted revocation, registrar, diagnostic CLI, and schema tests.
- [x] T017 Run the full Python unittest suite and static compile/diff checks.
- [x] T018 Run the read-only SpecKit analyze consistency review.
- [x] T019 Audit immutable core SHA and tracked/staged raw, archive, JSONL, and large-file gates.
- [x] T020 Review the final diff, mark completed tasks, commit, and push 137 `main` without any external asset.

## Dependencies

- T004 precedes T005-T006.
- T007 precedes T008-T010.
- T011 precedes T012-T013.
- T014-T015 depend on the final safety and diagnostic behavior.
- T016-T020 depend on all implementation tasks.

## Parallel opportunities

- Contract work T013 can proceed after the red diagnostic test shape is known.
- Documentation retraction T014 and CLI implementation T012 touch different files.

## MVP

T003-T006 are the immediate safety MVP; the remaining phases continue
annotation-independent progress without unblocking real 19/30 acceptance.
