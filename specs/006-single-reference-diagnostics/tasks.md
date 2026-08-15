# Tasks: 单人工样板驱动的无真值诊断

## Phase 1: Setup and Contracts

- [x] T001 Record the one-reference/25-unlabeled boundary in `specs/006-single-reference-diagnostics/evidence/baseline.json`
- [x] T002 [P] Add a versioned reference/index JSON Schema in `contracts/reference-anchored-diagnostics.schema.json`
- [x] T003 [P] Add failing reference/hash/path and LabelMe truth-leak tests in `tests/test_reference_anchored_diagnostics.py`

## Phase 2: User Story 1 - Development reference (P1)

**Independent Test**: matching review/comparison hashes produce one offline-only reference; mismatches fail.

- [x] T004 [US1] Implement strict development-reference construction in `tools/export_reference_anchored_diagnostics.py`
- [x] T005 [US1] Validate reference output against Schema and keep all paths/hash provenance safe in `tests/test_reference_anchored_diagnostics.py`

## Phase 3: User Story 2 - Per-image AUTO LabelMe diagnostics (P1)

**Independent Test**: one diagnostic per manifest image, successful geometry is exact and failures never fabricate values.

- [x] T006 [US2] Implement one-to-one manifest/result/hash validation in `tools/export_reference_anchored_diagnostics.py`
- [x] T007 [US2] Export AUTO circle/opening/axis/sidewall/rejected evidence with relative image paths in `tools/export_reference_anchored_diagnostics.py`
- [x] T008 [US2] Add success/failure, duplicate/missing result, traversal and in-worktree output tests in `tests/test_reference_anchored_diagnostics.py`

## Phase 4: User Story 3 - Honest observed deltas (P2)

**Independent Test**: circular reference observations are labeled non-accuracy and missing values remain null.

- [x] T009 [US3] Export diagnostic index and CSV with circular observation-only deltas in `tools/export_reference_anchored_diagnostics.py`
- [x] T010 [US3] Keep batch accuracy and static repeatability NOT_EVALUATED and test wraparound/null behavior in `tests/test_reference_anchored_diagnostics.py`
- [x] T011 [US3] Document the one-reference workflow in `README.md` and `specs/006-single-reference-diagnostics/quickstart.md`

## Phase 5: Real Data and Validation

- [x] T012 Run the external one-reference plus 25-JPEG export and record de-identified counts/hashes in `specs/006-single-reference-diagnostics/evidence/real-run.json`
- [x] T013 Run focused/full tests, Schema, CLI, JSON, diff and pollution checks; complete this task list
- [x] T014 Create one local commit on `003-a2-paired-notch-stability` without push/merge/PLC changes

## Dependencies

T001-T003 -> US1 -> US2 -> US3 -> real-data validation.

## Implementation Strategy

First lock the reference evidence boundary, then export per-image AUTO geometry, finally add observation-only comparison fields and real-data proof.
