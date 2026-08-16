# Tasks: A2固定阴影与真槽同源性

**Input**: Design documents from specs/020-fixture-shadow-groove-consistency/
**Tests**: TDD is mandatory for configuration, geometry, failure branches and runtime integration.

## Phase 1: Setup

- [x] T001 Record independently reproduced 480/302-frame statistics and the unverified relaxed-window caveat in specs/020-fixture-shadow-groove-consistency/evidence.md
- [x] T002 Verify current branch ancestry, clean worktree, protected main status and default-off 019 baseline in specs/020-fixture-shadow-groove-consistency/evidence.md
- [x] T003 Define experimental template and source-consistency fields in config/closed-loop-guidance-v3.fragment.json and contracts/slot-pose-config.schema.json

## Phase 2: Foundational

- [x] T004 Add strict default-off configuration parsing tests in tests/test_slot_pose_contract.py
- [x] T005 Implement fixture-shadow and source-consistency defaulting/validation in algorithms/slot_pose/contract.py
- [x] T006 Add shared circular sampling, normalization and bounded comparison helpers in algorithms/slot_pose/fixture_shadow.py
- [x] T007 Add source-consistency evidence model and validation helpers in algorithms/slot_pose/sidewall_consistency.py
- [x] T008 Run configuration and Schema tests before user-story implementation

## Phase 3: User Story 1 - 识别但不屏蔽固定阴影 (P1)

**Goal**: 输出两处固定阴影模板和成对证据，同时永不按固定角删除候选。
**Independent Test**: 合成候选位于31°/328°时仍保留，单影、双影、漂移和不相似对得到明确状态。

- [x] T009 [US1] Write failing template matching and fixed-angle non-deletion tests in tests/test_fixture_shadow.py
- [x] T010 [US1] Implement candidate profile extraction and per-template multi-evidence matching in algorithms/slot_pose/fixture_shadow.py
- [x] T011 [US1] Implement paired-shadow completeness and similarity assessment in algorithms/slot_pose/fixture_shadow.py
- [x] T012 [US1] Preserve raw and normalized intensity/gradient profiles in fixtureShadowEvidence through algorithms/slot_pose/legacy_adapter.py
- [x] T013 [US1] Add output contract compatibility tests for disabled and enabled template diagnostics in tests/test_slot_pose_contract.py
- [x] T014 [US1] Run fixture matcher tests and verify no fixed-angle candidate suppression

## Phase 4: User Story 2 - 拦截不同来源混合双边 (P1)

**Goal**: 对精修后的两侧壁执行不可互相抵消的同源硬门。
**Independent Test**: 真槽双壁通过；part-019形态、阴影双边、不对称、深度和终点不一致全部fail-closed。

- [x] T015 [US2] Write failing sidewall direction-normalization, profile-audit and hard-gate tests in tests/test_sidewall_consistency.py
- [x] T016 [US2] Extend subpixel sampling to retain canonical local gray, normalized gray, gradient, contrast and radial profiles in algorithms/slot_pose/groove_refinement.py
- [x] T017 [US2] Implement contrast, gradient, normalized-profile, radial-support and endpoint-structure hard gates in algorithms/slot_pose/sidewall_consistency.py
- [x] T018 [US2] Integrate source consistency after refinement and before single groove pose in algorithms/slot_pose/legacy_adapter.py
- [x] T019 [US2] Add GROOVE_SOURCE_INCONSISTENT fail-closed mapping and diagnostics in algorithms/slot_pose/legacy_adapter.py
- [x] T020 [US2] Add synthetic part-019 mixed-source regression without embedding real truth in tests/test_sidewall_consistency.py
- [x] T021 [US2] Verify legacy/paired/multi-role/default single-groove behavior remains unchanged in tests/test_single_real_groove.py
- [x] T022 [US2] Run sidewall and runtime integration tests

## Phase 5: User Story 3 - 安全分解槽与阴影重叠 (P2)

**Goal**: 在人工参考剖面存在时生成有上限残差假设；无参考、0解、多解和超限均安全失败。
**Independent Test**: 真槽在31°/328°重叠仍被保留，纯阴影、阴影加槽、无参考和多解状态可区分。

- [x] T023 [US3] Write failing overlap model comparison, hard-cap and 31°/328° non-mask tests in tests/test_fixture_shadow.py
- [x] T024 [US3] Implement fixture-only predicted profile and fixture-plus-groove residual hypotheses in algorithms/slot_pose/fixture_shadow.py
- [x] T025 [US3] Implement bounded residual interval extraction, circular deduplication and hypothesis provenance in algorithms/slot_pose/fixture_shadow.py
- [x] T026 [US3] Integrate only unique residual hypotheses into experimental candidate evaluation without mutating rawCandidates in algorithms/slot_pose/legacy_adapter.py
- [x] T027 [US3] Map missing reference, zero solution, multi-solution and overflow to diagnostic incomplete/ambiguous/failed states in algorithms/slot_pose/legacy_adapter.py
- [x] T028 [US3] Add invalid template/profile/hypothesis limit tests in tests/test_slot_pose_contract.py and tests/test_fixture_shadow.py
- [x] T029 [US3] Run overlap and fail-closed integration tests

## Phase 6: User Story 4 - 分组验证与标注队列 (P3)

**Goal**: 复算历史证据、保护part-006并生成part-019/015/021各两帧的明确物理shape队列。
**Independent Test**: 无图像即可验证统计、SHA泄漏拒绝、稳定队列和非准确率报告。

- [x] T030 [US4] Write failing historical-statistics, sealed leakage and queue-content tests in tests/test_fixture_shadow_governance.py
- [x] T031 [US4] Implement read-only historical evidence audit and strict/relaxed definition reporting in tools/audit_a2_fixture_shadow_evidence.py
- [x] T032 [US4] Update annotation shapes to explicit real_groove_boundary, fixture_shadow_a_region and fixture_shadow_b_region in tools/audit_a2_robustness_groups.py
- [x] T033 [US4] Generate deterministic two-frame queues for part-019/015/021 without prefilled truth in tools/audit_a2_fixture_shadow_evidence.py
- [x] T034 [US4] Add external experimental config materializer that cannot overwrite base in tools/prepare_slot_pose_fixture_shadow_config.py
- [x] T035 [US4] Add Mac paired default/experimental commands and interpretation rules in specs/020-fixture-shadow-groove-consistency/quickstart.md
- [x] T036 [US4] Run historical JSON audit without reading images or part-006 and record external artifact hashes in specs/020-fixture-shadow-groove-consistency/evidence.md

## Phase 7: Polish and Cross-Cutting Validation

- [x] T037 Update README.md, config/README.md and contracts/slot-pose-output.md with default-off, non-mask and source-consistency semantics
- [x] T038 Run focused tests, full unittest discovery and all JSON Schema validations
- [x] T039 Run 25-JPEG default versus experimental diagnostic only if inputs remain external; report compatibility and failure states without accuracy claims
- [x] T040 Measure default and experimental latency/RSS with method and environment recorded in specs/020-fixture-shadow-groove-consistency/evidence.md
- [x] T041 Run git diff --check, JSON parsing, media/archive/JSONL, absolute-path and added-large-file pollution audits
- [x] T042 Mark completed tasks, re-run SpecKit consistency analysis and record residual BLOCKED items in specs/020-fixture-shadow-groove-consistency/evidence.md
- [x] T043 Commit locally, push branch 020-fixture-shadow-groove-consistency without merging main, and report exact Mac commands

## Dependencies and Execution Order

- Phase 1 and Phase 2 block all user stories.
- US1 template evidence and US2 source consistency are independently testable after foundation.
- US3 depends on US1 profile/template evidence but not on US2 acceptance.
- Runtime candidate output depends on US1, US2 and US3 states.
- US4 governance is independent of image algorithm implementation after foundation.
- Phase 7 requires all desired user stories complete.

## Implementation Strategy

1. Establish strict default-off configuration and failing tests.
2. Deliver non-destructive fixture evidence before any overlap candidate changes.
3. Deliver sidewall source-consistency fail-closed gate and part-019 synthetic regression.
4. Add bounded residual hypotheses only when reference profiles exist.
5. Validate governance, external evidence, full compatibility and performance.
6. Push feature branch only; do not merge main.
