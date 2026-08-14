# Tasks: A2双缺口槽姿态稳定检测与真实数据验收

**Input**: Design documents from `specs/003-a2-paired-notch-stability/`

**Prerequisites**: `plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/`

**Tests**: 用户明确要求测试先行，覆盖Schema、CLI、批处理、失败分支、历史legacy回归和paired独立真值。

**Organization**: 任务按用户故事组织，但因本次由单一实施者且共享文件较多，默认按顺序执行。

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup and Compatibility Baseline

**Purpose**: 固定分支基线、配置边界和不可修改资产。

- [x] T001 在`config/inspection.example.json`加入显式诊断模式、目标语义未确认标志和paired门槛的fail-closed默认值（FR-005, FR-011, FR-012）
- [x] T002 在`contracts/slot-pose-config.schema.json`扩展可向后读取的profile/pairing配置约束，禁止未知模式和非法门槛（FR-005, FR-009）
- [x] T003 [P] 在`config/README.md`记录诊断模式与生产语义确认的分离规则（FR-011, FR-012）
- [x] T004 在`tests/test_slot_pose_contract.py`先写旧配置安全默认、新配置错误和未确认语义测试（FR-009..FR-013）

---

## Phase 2: Foundational Circular Geometry

**Purpose**: 为多候选、配对和评估建立单一环形数学语义。

- [x] T005 在`tests/test_angular_profile.py`先写环形差、环形中点、跨边界连通段和确定性排序测试（FR-004, FR-007）
- [x] T006 在`algorithms/slot_pose/angular_profile.py`实现无I/O的环形角工具、候选和配对数据类型（FR-004, FR-007）
- [x] T007 在`tests/test_slot_pose_evaluation.py`先写±180°环绕、静态环形展开和跨真值组残差统计测试（FR-018, FR-019）
- [x] T008 在`tools/evaluate_slot_pose.py`提供共用环形均值/展开和残差分组统计，失败不产生角度样本（FR-018, FR-019）

**Checkpoint**: 角度边界、候选边界和评估残差共享一致的环形语义。

---

## Phase 3: User Story 1 — 外缘多候选和双缺口诊断 (Priority: P1) 🎯 MVP

**Goal**: 从已有A端面外缘环带提取所有暗区并返回唯一双缺口中心线诊断。

**Independent Test**: 受控双缺口剖面和图像上的候选字段、配对中心线、唯一性和polar一致性可数值核对。

### Tests for User Story 1

- [x] T009 [US1] 在`tests/test_angular_profile.py`先写全暗区提取、中心/半宽/显著度/边界、次候选差距和多组合配对测试（FR-003, FR-004, FR-006）
- [x] T010 [US1] 在`tests/test_paired_slot_pose.py`先写平移、缩放、亮度/噪声和±180°环绕的paired独立真值测试（SC-002）
- [x] T011 [US1] 在`tests/test_legacy_adapter.py`先写两种显式模式的编排、参考/目标paired rotation和polar一致性测试（FR-001, FR-005, FR-008）

### Implementation for User Story 1

- [x] T012 [US1] 在`algorithms/slot_pose/angular_profile.py`实现环形平滑、中位数/MAD阈值、全连通暗区提取和可数值核对的候选摘要（FR-003, FR-004, SC-004）
- [x] T013 [US1] 在`algorithms/slot_pose/angular_profile.py`实现全组合硬门、得分、最佳/次佳差距、唯一性和环形中心线（FR-006, FR-007）
- [x] T014 [US1] 在`algorithms/slot_pose/legacy_adapter.py`调用历史`polar_resample`提取外缘剖面，先验证圆心/尺度/环带完整性，不新建圆/配准链（FR-002, FR-003, FR-008）
- [x] T015 [US1] 在`algorithms/slot_pose/legacy_adapter.py`保留legacy原路径并接入参考/目标paired、paired rotation、polar一致性及诊断输出（FR-001, FR-005, FR-008）
- [x] T016 [US1] 在`tools/generate_synthetic_paired_notches.py`生成小型paired参考、独立真值、变换正样本和不进Git的运行资产（SC-002, SC-009）

**Checkpoint**: paired正样本可独立通过，旧legacy模式的同源路径未改变。

---

## Phase 4: User Story 2 — 不可靠时安全失败 (Priority: P1)

**Goal**: 任何候选、配对、图像、一致性、配置或外部决策失败都不带正式角或旧值。

**Independent Test**: 缺一槽、多余暗区、双配对歧义、裁切、错误配置和未确认语义均得到稳定错误码和空角。

### Tests for User Story 2

- [x] T017 [US2] 在`tests/test_angular_profile.py`先写缺一槽、多余暗区、等价双配对、宽度/显著度/间距越界测试（FR-006, FR-009, SC-003）
- [x] T018 [US2] 在`tests/test_paired_slot_pose.py`先写裁切环带、圆心/尺度异常、polar不一致和未确认目标/机械语义测试（FR-008..FR-012）
- [x] T019 [US2] 在`tests/test_slot_pose_cli.py`先写错误模式/门槛配置、strict退出码和连续任务不复用旧角测试（FR-009, FR-010）

### Implementation for User Story 2

- [x] T020 [US2] 在`algorithms/slot_pose/contract.py`增加配置语义验证和稳定paired失败码，保持无效结果角/置信度为空（FR-009..FR-013）
- [x] T021 [US2] 在`algorithms/slot_pose/legacy_adapter.py`将候选/配对/裁切/一致性失败映射为稳定阶段和诊断（FR-008..FR-010）
- [x] T022 [US2] 在`algorithms/slot_pose/legacy_adapter.py`和`algorithms/slot_pose/main.py`对目标语义与机械约定分别门控，禁止技术模式自动成为机械角（FR-010..FR-012）

**Checkpoint**: 所有聚焦失败样本100% fail-closed，诊断可保留但不含正式角。

---

## Phase 5: User Story 3 — Mac A2批量验收 (Priority: P2)

**Goal**: 以外置Manifest和truth在Mac上分别评估正常集精度/稳定性和坏图误引导。

**Independent Test**: 小型外置目录、分组CSV、truth CSV和JSONL结果可完成一键流程，并拒绝分组/指纹/split污染。

### Tests for User Story 3

- [x] T023 [US3] 在`tests/test_data_tools.py`先写显式condition映射、dataset class、时序字段、不猜25×20和Manifest/truth一致性测试（FR-014..FR-017）
- [x] T024 [US3] 在`tests/test_slot_pose_evaluation.py`先写正常报告全指标、坏图false-positive、失败不填0和不完整状态测试（FR-018..FR-022）
- [x] T025 [US3] 在`tests/test_slot_pose_batch.py`先写单图失败不中断整批、逐图任务ID和一键产物测试（FR-010, FR-023, SC-006）

### Implementation for User Story 3

- [x] T026 [US3] 在`tools/make_manifest.py`支持显式分组映射、normal/bad、condition、capture timestamp/sequence和split，未分组时不猜测（FR-014, FR-015）
- [x] T027 [US3] 在`tools/validate_dataset.py`校验Manifest/truth指纹、分组、序号、数据集类别和物理样品/split隔离（FR-016, FR-017, SC-007）
- [x] T028 [US3] 在`tools/evaluate_slot_pose.py`分别生成正常/坏图报告，增加有效率、静态环形极差、跨组残差和false-positive指标（FR-018, FR-019, FR-020, FR-021, FR-022, SC-008）
- [x] T029 [US3] 在`tools/run_slot_pose_batch.py`确保逐图捕获输入/配置失败并持续处理，失败结果仍可追溯（FR-010, SC-006）
- [x] T030 [US3] 在`tools/run_a2_acceptance.py`组合Manifest生成/验证、批处理、truth校验和正常/坏图分报告的一键CLI（FR-023）
- [x] T031 [P] [US3] 在`data/README.md`和`specs/003-a2-paired-notch-stability/quickstart.md`固化Mac外置数据命令、分组证据和不入Git规则（FR-014, FR-015, FR-023, FR-024）

**Checkpoint**: 不含A2原图的小数据可完整演练Mac一键验收。

---

## Phase 6: User Story 4 — v2兼容与集成边界 (Priority: P3)

**Goal**: 旧v2消费者可忽略新诊断，且不产生任何PLC编码或写入。

**Independent Test**: 现有顶层/result/error断言和Schema对带新diagnostics的有效/无效样例仍成立。

### Tests for User Story 4

- [x] T032 [US4] 在`tests/test_slot_pose_contract.py`先写v2必填字段不变、新diagnostics可忽略、无效角不变量和无PLC字段测试（FR-010, FR-013, FR-025）

### Implementation for User Story 4

- [x] T033 [US4] 在`algorithms/slot_pose/contract.py`和`contracts/slot-pose-result.schema.json`保持result/2必填契约，将新数据限定为诊断扩展（FR-013）
- [x] T034 [P] [US4] 在`contracts/slot-pose-output.md`记录paired诊断向后兼容、过期结果禁用和PLC未确认禁写边界（FR-010, FR-013, FR-025）

---

## Phase 7: Polish and Full Validation

**Purpose**: 复跑全量门禁，检查污染并记录外部BLOCKED。

- [x] T035 在`tests/test_legacy_adapter.py`和基线命令复跑72角legacy扫角及3×20重复性，对比修改前MAE/P95/max、有效率和耗时（SC-001, SC-006）
- [x] T036 运行`tools/generate_synthetic_paired_notches.py`产生的paired全部正/负合成集，验证真值精度、门控失败率和默认未确认配置（SC-002, SC-003, SC-010）
- [x] T037 运行全量`unittest`、JSON Schema解析、`compileall`、`git diff --check`和CLI/批处理/一键冒烟（SC-005）
- [x] T038 检查Git差异中的原图/压缩包/派生大文件、绝对数据路径和禁止工作区指纹，在`README.md`记录分支、验证命令和B-001..B-005（FR-024, FR-025, SC-009）

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 → US2 → US3 → US4 → Polish。
- T004/T005/T007必须在对应配置/数学实现前先失败；每个用户故事的测试任务必须先于其实现任务。
- T014是新模块调用历史`polar_resample`的唯一入口；`angular_profile.py`不直接动态加载历史源。
- T022依赖T020/T021；T029/T030依赖US1/US2的稳定单图结果；T033依赖所有新诊断字段定型。
- 文档任务T003/T031/T034可与不修改同文件的实现任务并行；本次单实施者仍按顺序完成。

## Parallel Opportunities

- T003与T004可并行，因为分别修改文档和测试。
- T031可在T026-T030之后与报告验证并行。
- T034可与T033并行，但必须在新诊断名称冻结后开始。

## Implementation Strategy

1. 先固定配置和环形数学不变量。
2. 以US1交付多候选和双缺口诊断MVP，独立复跑legacy基线。
3. 以US2完成所有fail-closed分支，再进入数据工具。
4. 以US3完成Mac一键验收，以US4冻结v2兼容边界。
5. 最后复跑全量和两套合成基线，只做本地提交，不推送、不合并main。

---

## Phase 8: Drawing Evidence Correction & Generic Roles

- [x] T039 [US1] Audit the external drawing video hash and record bounded metadata in `specs/003-a2-paired-notch-stability/evidence/drawing-video-audit.json`
- [x] T040 [US1] Replace paired-first assumptions with generic datum/target roles and blockers in `specs/003-a2-paired-notch-stability/spec.md`
- [x] T041 [US1] Redesign primary entities around role assignment and drawing observations in `specs/003-a2-paired-notch-stability/data-model.md`
- [x] T042 [US1] Define separate drawing-angle truth and v2 diagnostic contracts in `specs/003-a2-paired-notch-stability/contracts/`
- [x] T043 [US1] Add exhaustive unique role assignment and circular geometry in `algorithms/slot_pose/role_assignment.py`
- [x] T044 [US1] Integrate `multi_notch_roles` and semantic gates in `algorithms/slot_pose/legacy_adapter.py`
- [x] T045 [US2] Add role/mapping/datum/output-purpose failure codes and validation in `algorithms/slot_pose/contract.py`
- [x] T046 [US1] Add wrap, extra-candidate, ambiguity, missing-role and datum-axis tests in `tests/test_role_assignment.py`
- [x] T047 [US1] Add integrated multi-notch fixtures and tests in `tools/generate_synthetic_multi_notches.py` and `tests/test_multi_notch_roles.py`
- [x] T048 [US2] Prove drawing inspection cannot become mechanical correction in `tests/test_multi_notch_roles.py`
- [x] T049 Update example configuration and workflow in `config/inspection.example.json` and `specs/003-a2-paired-notch-stability/quickstart.md`
- [x] T050 Run full regression, consistency analysis, pollution checks, and update `specs/003-a2-paired-notch-stability/evidence/server-validation-summary.json`

---

## Phase 9: Convergence

- [x] T051 Decouple `multi_notch_roles` profile/candidate extraction from the legacy single-notch success gate in `algorithms/slot_pose/legacy_adapter.py`, while preserving the unchanged legacy path and fail-closed result semantics per FR-003/FR-005/FR-007 (contradicts)
- [x] T052 Add a deterministic external-evidence review CLI with candidate-number overlays, candidate/role-hypothesis tables, confidence and ambiguity summaries, plus focused tests in `tools/render_slot_pose_review.py` and `tests/test_slot_pose_review.py` per FR-004 and Constitution III/IV (partial)
- [x] T053 Run the real A2 server inventory and diagnostic workflow outside Git, then record only path-free hashes, counts, failure distribution, bounded findings and minimum field questions in `specs/003-a2-paired-notch-stability/evidence/a2-server-diagnostic-summary.json` per FR-014/FR-024/SC-009 (partial)
- [x] T054 Add an optional normalized face-search ROI that masks adjacent fixtures before calling the unchanged historical circle/scale chain, including config validation, diagnostics and tests, while leaving it disabled by default per FR-001/FR-002/FR-027 (partial)

---

## Phase 10: Convergence

- [x] T055 Validate the 25-frame external JPEG diagnostic set, run both full-frame and development-ROI `multi_notch_roles` batches, and record only path-free hashes, aggregate results and bounded conclusions in repository evidence per FR-014/FR-020 and Constitution IV (partial)
- [x] T056 Extend `tools/render_slot_pose_review.py` to emit a deterministic failure-sample index and cover recursive JPEG manifests plus failed-result review artifacts in `tests/test_slot_pose_review.py` per FR-004/FR-027
- [x] T057 Add circular cross-frame candidate clustering, angle/prominence stability, circle/ring/role success rates, error distributions and latency P50/P95/max with tests and an external full-frame-versus-ROI summary per FR-018/FR-020 and Constitution III/IV

---

## Phase 11: Convergence — Single-Frame Groove Recognition

- [x] T058 [US1] Add test-first controlled polar evidence cases for true grooves, shadows, shallow fixture contacts, multiple grooves, weak/ambiguous grooves and 359/0 wrapping in `tests/test_groove_recognition.py` per FR-030..FR-033/SC-013
- [x] T059 [US1] Implement deterministic single-frame radial-depth, paired-edge, local-contrast and contour-consistency groove assessment in `algorithms/slot_pose/groove_recognition.py` per FR-031/FR-032
- [x] T060 [US2] Add groove-recognition configuration validation, safe defaults, v2 diagnostic contract fields and stable failure codes in `algorithms/slot_pose/contract.py`, `contracts/slot-pose-config.schema.json`, `config/inspection.example.json` and contract tests per FR-010/FR-013/FR-033
- [x] T061 [US1] Integrate raw-candidate → groove-filter → accepted-only role assignment in `algorithms/slot_pose/legacy_adapter.py`, preserving legacy/paired paths, and add multi-role integration tests proving rejected shadows cannot fill roles per FR-001/FR-030/FR-033
- [x] T062 [US1] Extend synthetic multi-notch fixtures and review artifacts to distinguish raw/rejected/accepted candidates with groove evidence in `tools/generate_synthetic_multi_notches.py`, `tools/render_slot_pose_review.py` and focused tests per FR-031/SC-013
- [x] T063 Run the 25-frame external JPEG development diagnostic with the new single-frame gate, visually audit the contact sheet without assigning authoritative roles, and record only path-free aggregate evidence in `specs/003-a2-paired-notch-stability/evidence/` per FR-024/FR-034/SC-009
- [x] T064 Re-run full unit, legacy and paired regressions plus schema/CLI/batch/pollution checks, then document the remaining original-BMP and field-label blockers per SC-001..SC-006/SC-009

---

## Phase 12: Physical Outer-Circle Correction

- [x] T065 [US1] Retract the alignment-radius-as-physical-boundary assumption in spec, plan, model and prior 25-frame evidence per FR-035
- [x] T066 [US1] Add test-first robust physical outer-circle refinement with offset prior, notch, fixture occlusion and missing-edge cases per FR-036/SC-014
- [x] T067 [US2] Gate multi-role candidate extraction on physical-circle quality and add the stable `PHYSICAL_OUTER_CIRCLE_FAILED` contract/config path
- [x] T068 [US1] Render alignment and physical circles distinctly, rerun the 25-frame external diagnostic, and visually inspect the corrected overlays
- [x] T069 Run full regression, schema, pollution and diff checks; record bounded corrected evidence without media or absolute paths

---

## Phase 13: Reuse gyj Physical-Circle Core

- [x] T070 [US1] Add tests proving the physical-circle stage delegates every radial edge decision and robust fit to the locked gyj source inventory
- [x] T071 [US1] Replace the parallel polar-threshold outer-circle implementation with gyj `outer_boundary_edge_point` + `robust_fit_circle`, retaining slot-specific coverage/residual gates
- [x] T072 [US2] Emit source function/hash provenance and preserve `PHYSICAL_OUTER_CIRCLE_FAILED` before all groove stages
- [x] T073 Run the 25-frame external JPEG diagnostic, generate overlays/contact sheet, and compare within-group/cross-group circle stability against the superseded implementation
- [x] T074 Run full, legacy72, schema and pollution regression, record bounded evidence, and commit locally without push/merge
- [x] T075 Add a path-safe, independently reviewed LabelMe manual-circle truth contract/exporter and focused tests

---

## Phase 14: Manual Open-Groove Geometry Review

- [x] T076 [US1] Add failing tests for variable point counts, finite coordinates, endpoint reversal, 359/0 midpoint, endpoint-to-circle gates, continuity, inward-depth shadow rejection, quadrant and target separation (FR-037..FR-041/SC-016)
- [x] T077 [US4] Add versioned manual-groove review JSON Schema and document image-angle/target contracts with runtime-truth isolation (FR-041..FR-043)
- [x] T078 [US1] Implement the external-only LabelMe groove review CLI by delegating circle fitting to the locked gyj source and generating a non-runtime semantic copy/report/overlay (FR-037..FR-043)
- [x] T079 Run the external 134-point/34-point manual sample without overwriting it; record only hashes, metrics and bounded conclusions in repository evidence (FR-043/SC-015)
- [x] T080 Re-run the external 25-JPEG no-truth diagnostic and report only retain/reject/failure/latency distributions (FR-034/FR-044)
- [x] T081 Run focused/full tests, Schema, legacy/paired regression, diff/pollution gates and commit locally without push or PLC/upstream changes (SC-001..SC-006/SC-016)

---

## Phase 15: Versioned Single Real-Groove Runtime Mode

- [x] T082 [US1] Add failing pure/integration tests for one accepted groove plus two rejected shadows, image-up azimuth/quadrant, zero and multiple accepted candidates, target separation and runtime truth isolation (FR-045..FR-049/SC-017)
- [x] T083 [US4] Extend config/result diagnostic contracts and Schema with explicit `single_real_groove` and `slot-single-real-groove-pose/1` while preserving result v2 fail-closed semantics (FR-047..FR-049/FR-051)
- [x] T084 [US1] Implement exact-one groove cardinality, single-groove image pose construction and adapter orchestration without role assignment or automatic mode switching (FR-045..FR-049)
- [x] T085 [US3] Extend review/summary tools to report single-groove geometry validity, image-azimuth availability, shadow rejection and datum-blocked mechanical guidance separately (FR-050)
- [x] T086 Run the external 25-JPEG set in `single_real_groove`, generate Git-external overlays/review/summary, and record only de-identified counts/hashes/limits (FR-050/SC-018)
- [x] T087 Run focused/full, Schema, legacy72, paired, CLI/batch/diff/pollution gates and commit locally without push/merge/PLC changes (FR-051/SC-001..SC-006)
