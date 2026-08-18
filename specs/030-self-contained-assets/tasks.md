# Tasks: Self-Contained Slot-Pose Assets

**Input**: Design documents from `/specs/030-self-contained-assets/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

## Phase 1: Setup and Contracts

- [x] T001 Record reviewed 029 configuration/asset hashes and external output boundary in evidence notes under the Git-external 030 evidence directory (FR-004, FR-017)
- [x] T002 [P] Add strict `path_mode` contract to `contracts/slot-pose-config.schema.json` (FR-001, FR-003)
- [x] T003 [P] Add `contracts/slot-pose-portable-bundle.schema.json` for versioned manifest validation (FR-008)

---

## Phase 2: User Story 1 — One-Bundle Mac Replay (P1)

**Goal**: Load and run from a relocatable bundle without external asset paths.

**Independent Test**: Move a temporary bundle, change CWD, remove source access, initialize adapter, and process a representative image.

- [x] T004 [US1] Add failing config-relative relocation/CWD/path-escape tests in `tests/test_slot_pose_contract.py` (FR-001–FR-003)
- [x] T005 [US1] Implement strict config-relative normalization in `algorithms/slot_pose/contract.py` without changing downstream adapter behavior (FR-001–FR-003)
- [x] T006 [US1] Add failing relocated adapter and tamper tests in `tests/test_slot_pose_portable_bundle.py` (FR-005, FR-014, FR-015)
- [x] T007 [US1] Implement bundle builder core/CLI in `tools/build_slot_pose_portable_bundle.py` with byte-preserving asset copy and fail-closed preflight (FR-004–FR-006, FR-009, FR-014–FR-015)
- [x] T008 [US1] Validate the P1 temporary-bundle tests independently and record results in tasks.md

---

## Phase 3: User Story 2 — Auditable Portable Package (P2)

**Goal**: Produce and independently verify one deterministic, fully described archive.

**Independent Test**: Build twice, compare hashes, validate manifest/checksums, and compare effective/replay behavior.

- [x] T009 [US2] Add failing manifest/checksum/no-leak/determinism/worktree/overwrite tests in `tests/test_slot_pose_portable_bundle.py` (FR-007–FR-011)
- [x] T010 [US2] Implement deterministic staging/archive and manifest emission in `tools/build_slot_pose_portable_bundle.py` (FR-006–FR-011)
- [x] T011 [US2] Implement independent read-only verification CLI in `tools/verify_slot_pose_portable_bundle.py` (FR-007–FR-009)
- [x] T012 [US2] Add effective-identity and source/portable equivalence tests in `tests/test_slot_pose_portable_bundle.py` (FR-012–FR-013)
- [x] T013 [US2] Build the real 030 bundle outside Git, independently verify it, rebuild for deterministic archive equality, and record hashes (SC-003, SC-004, SC-007)
- [x] T014 [US2] Replay frozen 140 images with reviewed and portable configs; compare the documented non-timing fields and write a Git-external equivalence report (SC-005)

---

## Phase 4: User Story 3 — Backward Compatibility (P3)

**Goal**: Preserve historical absolute-path configs and document migration.

**Independent Test**: Existing config/schema/runtime tests pass unchanged; explicit portable invalid cases fail.

- [x] T015 [US3] Add/confirm tests for omitted `path_mode` historical behavior and unchanged effective identity in `tests/test_slot_pose_contract.py` (FR-001, FR-012)
- [x] T016 [US3] Document absolute versus portable modes and one-bundle Mac workflow in `config/README.md` and `specs/030-self-contained-assets/quickstart.md` (FR-006–FR-007)

---

## Phase 5: Quality Gates and Handoff

- [x] T017 Run focused tests, relevant full tests, all root JSON Schemas, and `git diff --check`; record exact counts (SC-006)
- [x] T018 Run SpecKit converge; append and complete any genuine remaining work, otherwise preserve tasks byte-for-byte
- [x] T019 Commit and push only `030-self-contained-assets`; verify clean worktree/upstream and no main/PLC/HMI/sealed-part access (FR-016–FR-017)
- [x] T020 Provide the Mac operator one archive path/hash and a final prompt that requires no external asset lookup

## Dependencies and Execution Order

- T001–T003 establish contract/evidence boundaries.
- T004 must fail before T005; T006 must fail before T007.
- T009 must fail before T010–T011; T012 follows a functioning package.
- T013 precedes T014 so real replay uses the independently verified artifact.
- T015–T016 follow finalized semantics.
- T017–T020 are final gates in order.

## Traceability

- US1 / FR-001–FR-006, FR-014–FR-015: T004–T008
- US2 / FR-007–FR-013: T009–T014
- US3 / compatibility and migration: T015–T016
- Safety / FR-016–FR-017: T001, T017–T020

## Execution Evidence

- Focused portable/contract tests: 41 run, 1 existing environment-dependent test skipped, 0 failures.
- Full repository tests with the declared jsonschema test dependency: 579/579 passed.
- Root Draft 2020-12 schemas: 58/58 passed `check_schema`; portable manifest example and real provisional config validated.
- Frozen 140 relocation comparison: 140/140 exact under the documented allowlist; 99 valid and 41 unchanged fail-closed `GROOVE_REFINEMENT_FAILED` results.
- Effective configuration SHA-256 stayed `2901b557952248f44c7f1a8d0a3414f1320f915e6909246bb4268f16fe1182db`.
- Two provisional real-asset builds produced identical archive SHA-256; final commit-bound artifact and its hash are recorded only in the Git-external 030 evidence directory.
- SpecKit analyze found no cross-artifact inconsistency; converge found no missing implementation task and appended none.
