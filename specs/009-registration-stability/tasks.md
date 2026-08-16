# Tasks: Registration Stability Statistics

**Input**: Design documents from `specs/009-registration-stability/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required by the feature specification and Constitution.

**Organization**: Tasks are grouped by user story so each diagnostic behavior remains independently testable.

## Phase 1: Setup and safety baseline

**Purpose**: Preserve the clean 137-only starting state and immutable boundaries.

- [x] T001 Record starting HEAD, worktree state, immutable core SHA, and withdrawn-annotation exclusion in `specs/009-registration-stability/implementation.md`.
- [x] T002 Verify Python/output/raw-asset ignore patterns remain complete in `.gitignore` without touching external assets.

---

## Phase 2: User Story 1 - Review cross-frame registration stability (Priority: P1) 🎯 MVP

**Goal**: Produce deterministic linear and circular distributions for registration-valid frames.

**Independent Test**: Known synthetic records reproduce exact linear statistics, while `+179°/-179°` remains a tight circular cluster.

### Tests for User Story 1

- [x] T003 [US1] Add failing known-value linear-distribution tests in `tests/test_registration_diagnostic.py`.
- [x] T004 [US1] Add failing circular wrap and single-frame tests in `tests/test_registration_diagnostic.py`.

### Implementation for User Story 1

- [x] T005 [US1] Implement finite linear and circular distribution helpers in `tools/diagnose_main_housing_registration.py`.
- [x] T006 [US1] Implement registration-valid metric extraction, per-frame normalization, and selected-hypothesis matching in `tools/diagnose_main_housing_registration.py`.
- [x] T007 [US1] Add the stability object to batch summary construction in `tools/diagnose_main_housing_registration.py` without changing per-frame registration.

**Checkpoint**: Known multi-frame registration values are summarized deterministically without any acceptance feedback.

---

## Phase 3: User Story 2 - Preserve failed and sparse runs safely (Priority: P1)

**Goal**: Keep all-invalid, mixed, incomplete, and non-finite inputs strict and traceable.

**Independent Test**: All-invalid records produce zero/null distributions; mixed records count failures but aggregate only eligible finite values.

### Tests for User Story 2

- [x] T008 [US2] Add failing all-invalid, mixed-eligibility, missing-hypothesis, and non-finite tests in `tests/test_registration_diagnostic.py`.

### Implementation for User Story 2

- [x] T009 [US2] Implement per-metric safe exclusion and explicit zero/null empty distributions in `tools/diagnose_main_housing_registration.py`.

**Checkpoint**: Sparse/failing batches serialize with no NaN, fabricated geometry, or lost failure count.

---

## Phase 4: User Story 3 - Run the same review on Mac external data (Priority: P2)

**Goal**: Publish and exercise a versioned v2 batch contract and external command.

**Independent Test**: A synthetic Manifest produces a v2 summary that validates strictly and contains no measurement/candidate-status fields.

### Tests for User Story 3

- [x] T010 [US3] Add failing v2 Schema, CLI batch, provenance, and forbidden-field tests in `tests/test_registration_diagnostic.py`.

### Implementation for User Story 3

- [x] T011 [US3] Add `contracts/a-end-face-main-housing-registration-summary-v2.schema.json` while retaining the v1 contract.
- [x] T012 [US3] Version the batch output and document its stability fields and external Mac command in `README.md` and `specs/009-registration-stability/quickstart.md`.

**Checkpoint**: Server and Mac use the same image-free v2 registration-only workflow.

---

## Phase 5: Verification and delivery

**Purpose**: Prove traceability, safety boundaries, and repository hygiene.

- [x] T013 Run targeted registration diagnostic and Schema tests from `tests/test_registration_diagnostic.py`.
- [x] T014 Run full `tests/`, `compileall`, JSON parsing, and `git diff --check` gates.
- [x] T015 Run read-only SpecKit analyze for `specs/009-registration-stability/` and remediate any Constitution/coverage issue.
- [x] T016 Run a registration-only smoke with the accessible external representative image and `/tmp` output, without loading any LabelMe file.
- [x] T017 Audit `algorithms/end_face/core.py` SHA/diff, unchanged search/quality gates, forbidden fields, staged raw/archive/JSONL files, and files over 1 MiB.
- [x] T018 Complete `specs/009-registration-stability/implementation.md`, review the final diff, commit, and push detached `HEAD:main` to 137 origin.

## Dependencies & Execution Order

- T001-T002 establish the safety baseline.
- T003-T004 precede T005-T007.
- T008 precedes T009 and may reuse the US1 helpers.
- T010 precedes T011-T012.
- T013-T018 depend on all user-story phases.

## Parallel Opportunities

- T003 and T004 describe independent statistical behaviors but share one test file, so edits remain sequential.
- T011 contract work and T012 documentation can proceed independently after the v2 output shape is fixed.
- External smoke T016 and audit commands T017 are read-only apart from `/tmp` output and may be grouped after tests pass.

## Implementation Strategy

1. Deliver US1 as the MVP: deterministic distributions over known valid records.
2. Add US2 safe-empty and partial-observation behavior without changing eligibility.
3. Add US3 contract/CLI documentation after the exact output is stable.
4. Complete all gates before commit; real A2 values remain an external follow-up.
