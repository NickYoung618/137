# Tasks: 全局物理外圆边族选择

**Input**: Design documents from `specs/026-global-circle-edge-family/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: 本功能明确要求TDD；每个故事先写失败测试，再实现对应行为。

**Organization**: 任务按用户故事分组；所有运行数据和结果必须留Git外。

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 固化安全证据入口、配置契约和测试边界。

- [x] T001 依据quickstart冻结开发/正对照/held-out清单并执行物理组交集与禁用分组污染门，输出到`/home/ubuntu/disk/dzk/slot-pose-private-data/multi-edge-circle-026-validation/` per FR-014/SC-007
- [x] T002 [P] 在`contracts/physical-circle-edge-family-diagnostic.schema.json`定义有界运行时边族摘要Schema per FR-011/FR-016
- [x] T003 [P] 在`contracts/manual-circle-edge-family-analysis.schema.json`定义Git外161人工圆与逐射线投影报告Schema per FR-012/FR-013/FR-017
- [x] T004 在`contracts/slot-pose-config.schema.json`先加入默认关闭的`physical_outer_circle.edge_family_selection`严格嵌套配置契约，并在`tests/test_slot_pose_contract.py`补非法类型、范围、未知字段和默认兼容失败测试 per FR-001/FR-011

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 建立共享多峰语义和确定性族模型，阻塞所有运行时故事。

**⚠️ CRITICAL**: 以下任务完成前不得接入运行时或解封held-out。

- [x] T005 在`tests/test_circle_edge_family_trace.py`先写生产/诊断多峰语义一致、每射线有界、bright-to-dark、亚像素、候选重排与非有限输入TDD测试 per FR-001/FR-005/FR-006
- [x] T006 在`algorithms/slot_pose/circle_edge_candidates.py`基于锁定core已有采样/平滑/亚像素原语实现共享有界`outer_boundary_edge_candidates`，保持`algorithms/end_face/core.py`逐字节不变，并在`tools/trace_circle_edge_families.py`删除重复峰实现 per FR-001/FR-005/FR-017
- [x] T007 在`tests/test_physical_outer_circle.py`先写旋转等变三点种子、每射线唯一归属、同族多种子去重、固定迭代/容量和候选顺序不变性TDD测试 per FR-002/FR-006/FR-007/FR-015
- [x] T008 在`algorithms/slot_pose/physical_outer_circle.py`实现严格校验的默认关闭边族配置、确定性有界假设/归属/同族去重与有界诊断，不调用下游槽链 per FR-002/FR-016

**Checkpoint**: 多峰与边族基础能力可用，旧默认路径测试保持不变。

---

## Phase 3: User Story 1 - 多边缘恢复唯一物理外圆 (Priority: P1) 🎯 MVP

**Goal**: 恰好一个全局圆族时交给现有鲁棒拟圆和原质量门，并在141/161/441与161人工真值上成立。

**Independent Test**: 合成单真圆+错族+连续missing唯一通过；161运行时不读JSON但离线圆误差满足SC-002；145不回退。

### Tests for User Story 1

- [x] T009 [P] [US1] 在`tests/test_physical_outer_circle.py`先写唯一族调用现有robust fit恰好一次、原`_fit_quality`门不变、missing不补点和旧关闭路径等价测试 per FR-003/FR-004/FR-005
- [x] T010 [P] [US1] 在`tests/test_full_frame_circle_locator.py`先写可选多峰回调在sparse和final均透传、每阶段单次射线链且final独立唯一性测试 per FR-004/SC-003/SC-009
- [x] T011 [P] [US1] 在`tests/test_legacy_adapter.py`先写功能关闭时旧模块兼容、开启但缺多峰原语时初始化明确拒绝、直接物理圆路径接入测试 per FR-006/FR-011

### Implementation for User Story 1

- [x] T012 [US1] 在`algorithms/slot_pose/physical_outer_circle.py`将唯一预选族交给现有`robust_fit_circle`一次并原样执行现有质量/sector证据，将`edgeFamilySelection`嵌入诊断 per FR-003/FR-004/FR-016
- [x] T013 [US1] 在`algorithms/slot_pose/full_frame_circle_locator.py`以可选关键字依赖接入sparse/final相同边族策略，禁止重复解码或重复每阶段射线采样 per FR-004/SC-009
- [x] T014 [US1] 在`algorithms/slot_pose/legacy_adapter.py`与`algorithms/slot_pose/contract.py`按显式开关传递共享多峰原语并保持旧外部模块/直接路径兼容 per FR-006/FR-011
- [x] T015 [US1] 用开发清单141/161/441与145正对照生成Git外候选回放，核对唯一族、原质量门、161中心/半径/人工弧P95和145不回退 per SC-002/SC-003/SC-004

**Checkpoint**: 唯一物理外圆可独立恢复并通过原质量门；尚未解封held-out。

---

## Phase 4: User Story 2 - 缺失或多圆族安全失败 (Priority: P1)

**Goal**: 无族、多同心/非同心合格族、裁切、反光和overflow均明确失败且无姿态。

**Independent Test**: 合成0/2族、两个同心真圆、两个非同心等价族、短弧、裁切、反光与容量溢出100%无角度；31°/328°无特殊分支。

### Tests for User Story 2

- [x] T016 [P] [US2] 在`tests/test_physical_outer_circle.py`先写无峰/少支持/低覆盖/两个同心合格族/两个非同心族/overflow/非有限证据失败测试 per FR-003/FR-008/SC-005
- [x] T017 [P] [US2] 在`tests/test_full_frame_circle_locator.py`先写多边族在sparse或final传播ambiguous且不得由分数、强度、先验距离或枚举顺序强选测试 per FR-003/FR-006
- [x] T018 [P] [US2] 在`tests/test_single_real_groove.py`先写圆族无族/歧义/overflow时当前角、调整角、方向、PLC和机械量全null的端到端测试 per FR-009/FR-010
- [x] T019 [P] [US2] 在`tests/test_circle_edge_family_trace.py`先写31°/328°、跨0°循环旋转和候选重排等变测试 per FR-007/FR-015/SC-006

### Implementation for User Story 2

- [x] T020 [US2] 在`algorithms/slot_pose/physical_outer_circle.py`完成`no_qualified_edge_family`、`ambiguous_edge_families`、`family_search_overflow`与非有限证据fail-closed分支 per FR-003/FR-008
- [x] T021 [US2] 在`algorithms/slot_pose/full_frame_circle_locator.py`和`algorithms/slot_pose/legacy_adapter.py`将多族传播为`HOUSING_CIRCLE_AMBIGUOUS`、其他族失败保留圆阶段原因且禁止下游角度 per FR-009/FR-011
- [x] T022 [US2] 在`config/inspection.example.json`与`config/README.md`记录默认关闭配置、0/多族语义、无固定角mask及与sector robustness的执行顺序 per FR-007/FR-011

**Checkpoint**: 失败关闭故事可独立通过全部合成与端到端测试。

---

## Phase 5: User Story 3 - 可复现根因与跨零件验收 (Priority: P2)

**Goal**: 生成不进入运行时的161报告，显式物化v3剖面，并用物理隔离held-out验证。

**Independent Test**: 161报告复现SHA/LabelMe/圆/LOO/逐射线统计；281/401圆链兼容且后续继续正确失败；全部数据留Git外。

### Tests for User Story 3

- [x] T023 [P] [US3] 在`tests/test_manual_circle_edge_family_analysis.py`先写SHA、LabelMe尺寸/标签/linestrip/88点/有限坐标、人工圆/LOO、逐射线投影、Git外输出与运行时不可导入测试 per FR-012/FR-013/FR-017
- [x] T024 [P] [US3] 在`tests/test_single_shot_initial_profile.py`先写新v3剖面显式开启边族选择、保留85°±5°/0.12同源性/ambiguity resolution/PLC false且v2不变测试 per FR-010/FR-018

### Implementation for User Story 3

- [x] T025 [US3] 在`tools/analyze_manual_circle_edge_families.py`实现只读161人工圆、leave-one-out、所有峰投影、旧选择归属、missing/switch区与SHA报告CLI，并用`contracts/manual-circle-edge-family-analysis.schema.json`验证 per FR-012/FR-013/SC-001
- [x] T026 [US3] 在`tools/prepare_single_shot_initial_config.py`与对应审计Schema中物化显式v3候选配置，保持v2不变且不写入任何人工/样本身份 per FR-006/FR-011/FR-018
- [x] T027 [US3] 运行161离线CLI并将报告写入`/home/ubuntu/disk/dzk/slot-pose-private-data/multi-edge-circle-026-validation/`，回读Schema与SHA并核对SC-001/SC-002 per FR-012/FR-013/SC-001
- [x] T028 [US3] 冻结代码和候选配置后解封281/401 held-out回放，确认圆仍通过、后续分别`GROOVE_RECOGNITION_FAILED`/`GROOVE_REFINEMENT_FAILED`且姿态/PLC全null per FR-014/SC-007

**Checkpoint**: 三个用户故事均具备可复现、跨物理零件证据。

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 完整质量门、性能、污染审计和交付。

- [x] T029 [P] 按`specs/026-global-circle-edge-family/quickstart.md`运行聚焦测试、全量测试和全部根Schema，并修复任何回归 per SC-008
- [x] T030 使用同机同清单热适配器运行基线/候选成对性能与静态重复性，报告P50/P95/max、候选/种子上界且总P95≤2.5秒 per FR-016/SC-009
- [x] T031 执行`git diff --check`、大文件/图片/JSONL、私有绝对路径、人工label、样本/固定角度特判与禁用分组污染门 per FR-006/FR-007/FR-014/FR-017/SC-008
- [x] T032 更新`specs/026-global-circle-edge-family/quickstart.md`与Git外证据索引，记录修改前后指标、失败分布、限制和不宣称生产准确率 per FR-014/FR-017/SC-007
- [x] T033 核对`tasks.md`全部完成后提交并推送`026-global-circle-edge-family`独立分支，确认未合并main、未修改PLC/HMI per FR-018

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1无依赖。
- Phase 2依赖Phase 1并阻塞全部用户故事。
- US1与US2均依赖Phase 2；为避免同文件冲突按US1后US2执行。
- US3的离线测试可在Phase 2后开始，但v3物化与held-out解封依赖US1/US2完成。
- Phase 6依赖全部用户故事完成。

### User Story Dependencies

- **US1**: 提供唯一族成功路径，是MVP。
- **US2**: 复用US1族模型，补齐安全失败，交付不可缺少。
- **US3**: 证据工具可独立测试，最终跨零件验收依赖US1/US2。

### Within Each User Story

- 测试任务必须先运行并确认因缺功能失败，再写实现。
- 同一源文件任务顺序执行。
- 开发组通过并冻结配置后才能解封held-out。
- 任何原质量门、槽同源性门、PLC或main变化都必须立即停止。

### Parallel Opportunities

- T002与T003可并行。
- T009、T010、T011作用于不同测试文件，可并行编写。
- T016至T019作用于不同测试边界，可并行编写。
- T023与T024可并行。
- T029的测试门可与文档证据整理并行，但T030/T031需针对同一冻结提交执行。

## Parallel Example: User Story 1

```text
Task: T009 tests/test_physical_outer_circle.py 唯一族/原质量门TDD
Task: T010 tests/test_full_frame_circle_locator.py sparse/final透传TDD
Task: T011 tests/test_legacy_adapter.py 兼容与依赖TDD
```

## Implementation Strategy

### MVP First

1. 完成Setup与Foundational。
2. 完成US1唯一族成功路径。
3. 仅用开发组与145验证；不解封held-out。
4. US2安全失败全过后才允许进入US3最终验收。

### Incremental Delivery

1. 多峰语义和族模型。
2. 唯一族成功路径。
3. 0/多族fail-closed与错误传播。
4. 离线证据、v3剖面和held-out。
5. 全门禁、提交与推送。

## Notes

- `[P]`只标记不同文件且无未完成依赖的任务。
- 所有任务含明确路径和FR/SC追踪。
- 图片、LabelMe、manifest派生物和JSONL不得提交Git。
- 不读取sealed part-006，不合并main，不触碰PLC/HMI。
