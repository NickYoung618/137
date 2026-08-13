# Tasks: A端面槽姿态估计（历史核心复用适配）

**Input**: Design documents from `/home/ubuntu/disk/dzk/槽姿态引导算法/specs/002-slot-pose-estimation/`

**Prerequisites**: `plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/`

**Tests**: 按用户要求采用测试先行；所有视觉测试调用历史核心或小型合成资产，不另写独立视觉算法。

**Reuse boundary**: `/home/ubuntu/disk/gyj/HousingInspectionDemo/algorithms/a_end_face/main.py`只读；新代码仅为
加载/哈希校验、契约适配、机械语义、质量门禁、测试和评估。

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup and Provenance

**Purpose**: 固定依赖、权威资产和不可修改边界。

- [x] T001 在`pyproject.toml`和`uv.lock`加入与历史源兼容的NumPy依赖并保持Pillow固定版本（FR-023）
- [x] T002 在`config/inspection.example.json`加入历史源/标注/参考图绝对路径与SHA-256、机械语义确认标志和质量门限（FR-007, FR-023, FR-024）
- [x] T003 校验并记录`specs/002-slot-pose-estimation/evidence/historical-a-end-face-reference-baseline.json`的函数清单和参考图数值（SC-008）
- [x] T004 更新`.gitignore`和`data/README.md`，明确A2原图/RAR不进服务器仓库及Mac推荐目录（FR-013, FR-014）

---

## Phase 2: Foundational Contracts

**Purpose**: 在任何有效角度实现前固定数据、配置和失败不变量。

- [x] T005 将配置设计落到根目录`contracts/slot-pose-config.schema.json`并覆盖历史资产、零位、正方向、范围和确认门禁（FR-007, FR-008, FR-023）
- [x] T006 将标注设计落到根目录`contracts/slot-pose-annotation.schema.json`并覆盖face、slot、真值、样品分组和split（FR-015, FR-016）
- [x] T007 将结果v2设计落到`contracts/slot-pose-result.schema.json`和`contracts/slot-pose-output.md`，固定有效/无效、资产指纹、时间和错误码（FR-009..FR-012）
- [x] T008 在`tests/test_slot_pose_contract.py`先写结果v2、未确认语义、空角度和资产指纹契约测试（FR-008..FR-012）
- [x] T009 在`algorithms/slot_pose/contract.py`实现结果v2构造/校验和稳定错误码，使T008通过（FR-008..FR-012）

**Checkpoint**: 任何检测接入前，未确认坐标和失败结果均不能携带正式角度。

---

## Phase 3: User Story 1 — 复用历史核心获得离线槽方向 (Priority: P1) 🎯 MVP

**Goal**: 哈希校验后只读调用历史端面中心、notch和polar旋转函数，并映射为槽姿态候选与正式角度。

**Independent Test**: 参考图复现证据基线；小型合成参考/旋转图通过相同历史函数得到预期相对角。

### Tests for User Story 1

- [x] T010 [US1] 在`tests/test_legacy_adapter.py`先写源/标注/参考图哈希不匹配、函数缺失和禁止修改权威目录测试（FR-022, FR-023, SC-008）
- [x] T011 [US1] 在`tests/test_legacy_adapter.py`先写参考图notch/polar数值基线测试（FR-024, SC-008）
- [x] T012 [US1] 在`tests/test_slot_pose_cli.py`先写已确认合成配置的角度范围、正负方向和图像/配置/资产追溯测试（FR-001, FR-006, FR-007, FR-012）

### Implementation for User Story 1

- [x] T013 [US1] 在`algorithms/slot_pose/legacy_adapter.py`实现SHA-256校验、必需函数清单校验和不写字节码的只读动态加载（FR-022, FR-023）
- [x] T014 [US1] 在`algorithms/slot_pose/legacy_adapter.py`调用`build_reference_model`、`load_detection_gray`、`estimate_global_transform`、`find_outer_notch_angle`、`estimate_rotation_by_notch`和`estimate_rotation_by_polar`并返回现有质量量（FR-002, FR-003, FR-004, FR-005, FR-024）
- [x] T015 [US1] 在`algorithms/slot_pose/legacy_adapter.py`实现配置驱动的机械零位、cw/ccw符号、环绕和角度范围映射，不增加视觉检测逻辑（FR-006..FR-008）
- [x] T016 [US1] 在`tools/generate_synthetic_slot_pose.py`生成小型双圆+外缘notch参考/扫角图、LabelMe标注、真值CSV和显式测试配置（FR-021, SC-001, SC-002）
- [x] T017 [US1] 在`algorithms/slot_pose/main.py`接入legacy adapter和结果v2契约，保留单图CLI与strict退出码（FR-001, FR-010, FR-012）

**Checkpoint**: 参考图和合成图均通过历史核心；没有任何平行圆/极坐标/notch算法。

---

## Phase 4: User Story 2 — 不可靠时禁止引导 (Priority: P1)

**Goal**: 对资产、输入、notch、质量、语义和范围失败返回可区分且无角度的结果。

**Independent Test**: 篡改哈希、空白/无槽合成图、低显著度、polar/notch分歧和默认未确认配置全部fail-closed。

### Tests for User Story 2

- [x] T018 [US2] 在`tests/test_slot_pose_contract.py`先写`INPUT_INVALID`、`ASSET_MISMATCH`、`FACE_NOT_FOUND`、`SLOT_NOT_FOUND`、`SLOT_ROTATION_INCONSISTENT`、`QUALITY_REJECTED`、`POSE_CONVENTION_UNCONFIRMED`和`ANGLE_OUT_OF_RANGE`测试（FR-010, FR-011, SC-003）
- [x] T019 [US2] 在`tests/test_legacy_adapter.py`先写notch显著度、polar分数、旋转一致性和尺度质量门限测试（FR-009, FR-024）
- [x] T020 [US2] 在`tests/test_slot_pose_cli.py`先写无效结果不含正式角度、strict返回1且不复用上一任务结果的集成测试（FR-010..FR-012）

### Implementation for User Story 2

- [x] T021 [US2] 在`algorithms/slot_pose/legacy_adapter.py`实现只基于现有输出的质量组合与保守拒绝，不构造第二候选检测器（FR-009, FR-024, FR-025）
- [x] T022 [US2] 在`algorithms/slot_pose/contract.py`和`algorithms/slot_pose/main.py`完成异常到稳定错误码/阶段的映射与逐任务无状态处理（FR-010..FR-012）

**Checkpoint**: 任一失败均无正式角度；诊断候选不能被解释为可引导结果。

---

## Phase 5: User Story 3 — 数据、标注与验收闭环 (Priority: P2)

**Goal**: 为Mac A2后续回放提供Manifest、标注契约、角度误差/重复性/成功率/节拍评估，不传大图。

**Independent Test**: 合成结果和真值可生成完整评估；样本不足或真值缺失时状态明确不完整。

### Tests for User Story 3

- [x] T023 [US3] 在`tests/test_slot_pose_evaluation.py`先写环形角度误差、静态/动态重复性、成功/漏检/误检、错误码和耗时统计测试（FR-017, FR-018, FR-019）
- [x] T024 [US3] 在`tests/test_data_tools.py`补充A2推荐目录的Manifest分组、哈希和同物理样品split隔离验证测试（FR-013, FR-014, FR-016）

### Implementation for User Story 3

- [x] T025 [US3] 在`tools/evaluate_slot_pose.py`实现JSONL结果+真值评估和`INCOMPLETE/NOT_EVALUATED`状态（FR-017, FR-018, FR-019, SC-007）
- [x] T026 [US3] 在`data/README.md`和`config/README.md`记录A2 RAR流式/解压目录、标注字段、真值来源、40/20/20/20按样品隔离及20次采集规则（FR-013..FR-019）
- [x] T027 [US3] 用`tools/make_manifest.py`和`tools/validate_dataset.py`验证`/tmp`合成数据并在`specs/002-slot-pose-estimation/quickstart.md`固化命令（FR-014, SC-005）

**Checkpoint**: 服务器不含A2大图，Mac可按相同代码和契约执行正式验证。

---

## Phase 6: User Story 4 — PLC/机器人安全接口边界 (Priority: P3)

**Goal**: 固定逻辑接口和禁写门禁，不连接或写入真实PLC/机器人。

**Independent Test**: PLC映射未确认时任何结果都不产生地址、DInt编码或控制写入。

- [x] T028 [US4] 在`contracts/slot-pose-output.md`记录taskId、时间、valid、角度、置信度、错误码、超时和禁止旧值规则（FR-020）
- [x] T029 [US4] 在`tests/test_slot_pose_contract.py`加入`production_plc_mapping_confirmed=false`时无PLC编码字段的契约测试（FR-020）
- [x] T030 [US4] 在`config/inspection.example.json`和`README.md`列出B-001..B-005负责人/关闭顺序与本机A2运行命令，不填真实PLC地址（FR-020, SC-006）

---

## Phase 7: Polish and Validation

- [x] T031 在`tests/test_legacy_adapter.py`加入权威参考图运行时间和数值回归，验证源文件运行前后SHA-256不变（SC-004, SC-008）
- [x] T032 运行`uv run python -m unittest discover -s tests -v`、JSON Schema解析、`compileall`、`git diff --check`并修复失败项
- [x] T033 按`specs/002-slot-pose-estimation/quickstart.md`运行至少72个角度的合成扫角、单图strict、默认参考图fail-closed、Manifest和评估冒烟并记录输出路径（SC-001, SC-002, SC-003, SC-007）
- [x] T034 更新`README.md`，明确“复用代码”与“新写代码”、绝对路径、运行命令、已知质量缺口和Mac A2阻塞

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 → US2 → US3 → US4 → Polish。
- US1测试T010-T012必须先于T013-T017；US2测试T018-T020先于T021-T022；US3测试T023-T024先于T025-T027。
- T013是所有历史函数调用的唯一入口；其他新模块不得动态加载或复制历史视觉函数。
- T017依赖T009、T013-T015；T022依赖T017和T021；T025依赖T009的结果v2。

## Implementation Strategy

MVP为Phase 1至US2：复现历史参考基线、合成角度回归和fail-closed。US3提供Mac正式验证工具，US4只
固定接口边界。B-001至B-005不作为服务器代码任务伪关闭；它们阻塞生产验收但不阻塞MVP。

## Deferred External Field Work

- 现场/机械负责人：确认目标槽是否就是`find_outer_notch_angle`检测的外缘缺口（B-001）。
- 数据负责人戴泽楷：在Mac建立A2 Manifest/标注并确认与服务器历史参考的相机工位映射（B-002）。
- 机械/机器人负责人：给出机械零位、正方向和坐标映射（B-003）。
- 质量负责人：确认角度误差、重复性、成功率和节拍验收门限（B-004）。
- PLC/机器人工程师：确认字段、地址、缩放、握手、超时和失败动作（B-005）。
- 执行顺序：B-001/B-002 → B-003 → Mac冻结验证集 → B-004验收 → B-005上线；任何一步不能由算法默认值替代。
