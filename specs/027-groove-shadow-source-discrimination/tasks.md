# Tasks: 真实槽与固定装置阴影源判别

**Input**: Design documents from `/specs/027-groove-shadow-source-discrimination/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: 用户明确要求单元测试、真实回归和Schema验证；测试任务先于对应实现。

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 固定证据、分支和不变门限基线。

- [x] T001 记录A2包、700张结果流、配置和失败/overlay索引SHA及只读用途到`specs/027-groove-shadow-source-discrimination/evidence-baseline.md`
- [x] T002 记录026祖先提交、当前分支、禁止项和所有锁定recognition/refinement/polar/source/ambiguity门限到`specs/027-groove-shadow-source-discrimination/evidence-baseline.md`
- [x] T003 [P] 将设计期诊断和离线报告Schema复制为正式契约`contracts/groove-shadow-source-diagnostic.schema.json`与`contracts/groove-shadow-source-report.schema.json`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 建立配置、纯数据结构和Schema约束，禁止新模块拥有可调数值阈值。

- [x] T004 [P] 先为默认关闭、严格字段、依赖关系和门限不变性新增失败测试到`tests/test_slot_pose_contract.py`
- [x] T005 [P] 先为诊断Schema三态、not_evaluated、有界三候选和非有限拒绝新增失败测试到`tests/test_groove_shadow_discrimination.py`
- [x] T006 在`algorithms/slot_pose/groove_shadow_discrimination.py`实现默认配置合并、纯证据数据规范化和稳定枚举
- [x] T007 在`algorithms/slot_pose/contract.py`和`contracts/slot-pose-config.schema.json`增加严格默认关闭配置及single-real-groove/v2 refinement/original source-consistency/ambiguity依赖
- [x] T008 [P] 在`config/inspection.example.json`与`config/README.md`记录禁用示例、依赖和新物理验收前不得生产启用

**Checkpoint**: 配置和证据模型可独立验证，未改变运行时行为。

---

## Phase 3: User Story 1 - 逐图解释近阴影失败 (Priority: P1) 🎯 MVP

**Goal**: 对207张冻结失败索引生成唯一逐图失败阶段账本，不改变原结果、不伪造未运行证据或人工类别。

**Independent Test**: 联结冻结failure-index和700结果JSONL，得到207个唯一图像SHA；原错误/阶段一致，46张ambiguity的全部accepted候选（每张至少两个、最多三个）逐候选精修状态为not_evaluated，20张quality保留polar分数和空输出。

### Tests for User Story 1

- [x] T009 [P] [US1] 为SHA联结、重复/遗漏、错误阶段映射和安全空输出新增测试到`tests/test_trace_groove_shadow_sources.py`
- [x] T010 [P] [US1] 为ambiguous未运行证据、quality后置终止和human class不可推断新增测试到`tests/test_trace_groove_shadow_sources.py`

### Implementation for User Story 1

- [x] T011 [US1] 在`tools/trace_groove_shadow_sources.py`实现只读failure-index/overlay-index/normal+bad JSONL按SHA联结和规范化阶段映射
- [x] T012 [US1] 在`tools/trace_groove_shadow_sources.py`实现有界候选证据提取、not_evaluated传播、CSV/JSON报告及阶段计数
- [x] T013 [US1] 用冻结输入生成Git外`027-observed-diagnostic-trace-*`报告并在`specs/027-groove-shadow-source-discrimination/evidence-baseline.md`记录输出SHA与207行核对结果

**Checkpoint**: US1可独立回答每张失败图执行到哪里，但不声称逐图A/B真值。

---

## Phase 4: User Story 2 - 区分完整近阴影与混合遮挡 (Priority: P1)

**Goal**: 只用现有图像/几何门输出三态来源诊断；唯一完整真槽可沿既有链继续，混合、遮挡、歧义、缺证据和低polar均fail-closed。

**Independent Test**: 合成候选证据覆盖唯一存活、零存活混合、多个存活、未评估、非有限、容量溢出、候选重排/ID改名/整体旋转和低polar；关闭时026结果不变。

### Tests for User Story 2

- [x] T014 [P] [US2] 为三态状态机、所有竞争者明确失败条件和低polar不放行新增测试到`tests/test_groove_shadow_discrimination.py`
- [x] T015 [P] [US2] 为候选重排、ID改名、角度整体旋转、有限亮度变换和容量溢出新增测试到`tests/test_groove_shadow_discrimination.py`
- [x] T016 [P] [US2] 为单候选、多候选、refinement/source失败的适配器诊断与全空失败输出新增测试到`tests/test_single_real_groove.py`
- [x] T017 [P] [US2] 为既有ambiguity resolver逐候选证据完整性和原门限不变新增测试到`tests/test_groove_resolution.py`

### Implementation for User Story 2

- [x] T018 [US2] 在`algorithms/slot_pose/groove_shadow_discrimination.py`实现无新阈值的唯一存活/混合证据/不确定三态裁决和有界诊断
- [x] T019 [US2] 在`algorithms/slot_pose/legacy_adapter.py`收集粗识别、v2双壁、外圆肩部端点、原始source-consistency与全局门结果并调用纯裁决器
- [x] T020 [US2] 在`algorithms/slot_pose/groove_resolution.py`补齐每个accepted候选的稳定物理精修/source证据摘要，不改变候选选择语义
- [x] T021 [US2] 将`grooveShadowSourceDiscrimination`嵌套诊断接入结果并用`contracts/groove-shadow-source-diagnostic.schema.json`验证，保持根结果Schema兼容
- [x] T022 [US2] 验证关闭功能时026聚焦真实回归和现有测试无变化，并把代码/配置门限diff写入Git外回归报告

**Checkpoint**: US2实现可解释来源裁决但仍默认关闭；未通过独立物理验收，不进入生产profile。

---

## Phase 5: User Story 3 - 物理分离的冻结验收 (Priority: P2)

**Goal**: 支持新物理零件组一次性验收并明确当前缺数阻塞。

**Independent Test**: 验收工具拒绝与700物理ID重叠、缺人工三态、SHA变化或包含sealed part-006的manifest；合规组输出分类计数、安全空输出、重复性和性能。

### Tests for User Story 3

- [x] T023 [P] [US3] 为物理ID交集、缺标签、SHA漂移和sealed part-006拒绝新增测试到`tests/test_trace_groove_shadow_sources.py`
- [x] T024 [P] [US3] 为有原图/无原图两种representative overlay状态新增测试到`tests/test_slot_pose_review.py`

### Implementation for User Story 3

- [x] T025 [US3] 在`tools/trace_groove_shadow_sources.py`增加独立acceptance manifest预检、冻结SHA、分类/阶段/安全/性能聚合和阻塞状态
- [x] T026 [US3] 在`tools/render_slot_pose_review.py`增加候选来源、失败门、三态类别和选中候选的代表性叠加；无原图时只记录unavailable
- [ ] T027 [US3] 在新物理零件manifest到达后只读证明其与700物理分离且无sealed part-006，并记录到Git外验收目录
- [ ] T028 [US3] 冻结代码与配置后运行新物理零件一次性回放，报告完整近阴影安全放行/继续拒绝、混合遮挡全部拒绝、其他阶段、重复性与热态P95

**Checkpoint**: T027–T028依赖用户提供新物理零件；未到达时状态必须为`INDEPENDENT_ACCEPTANCE_BLOCKED`。

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 完成文档、全仓验证和可审计交付，不提前授权生产。

- [x] T029 [P] 更新`README.md`与`config/README.md`说明来源诊断、observed/acceptance数据边界和默认关闭状态
- [x] T030 运行聚焦测试、全仓测试、根Schema、026真实回归、`git diff --check`和热态P95并把命令/数量/SHA写入Git外验证报告
- [x] T031 核对所有无效结果角度/方向/修正/机械/PLC为空、`plcExecutionAuthoritative=false`，并确认PLC/HMI/main/sealed part-006均未触碰
- [x] T032 在`specs/027-groove-shadow-source-discrimination/quickstart.md`复核实际命令和产物路径并记录独立验收是否仍阻塞
- [x] T033 提交并推送`027-groove-shadow-source-discrimination`开发分支，报告提交SHA、测试数量、工作树状态且不合并main

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1/US2；US1账本和US2纯裁决可在Foundation后分别推进。
- US2运行时集成依赖T006–T007和T014–T017测试。
- US3工具开发依赖US1报告模型；真实执行T027–T028依赖外部新物理数据，不能用700张替代。
- Polish依赖所有可执行开发任务；T033可以提交默认关闭的开发实现，但不能把T027–T028伪标完成。

## Parallel Opportunities

- T003、T004、T005、T008在不修改同一文件时可并行。
- US1测试与US2纯函数测试可并行准备。
- T023和T024可并行；真实验收必须顺序执行“冻结→无交集检查→一次回放”。

## Implementation Strategy

### MVP First

1. 固定证据和门限。
2. 完成严格配置与纯证据模型。
3. 生成207行逐图失败账本，先解决“发生在哪一阶段”的可解释性。
4. 在不改结果的情况下审阅账本，再接入三态运行时诊断。

### Safe Incremental Delivery

1. 默认关闭提交纯诊断和工具。
2. 合成测试证明状态机的顺序/ID/旋转不变与fail-closed。
3. 026回归证明关闭时兼容。
4. 等新物理零件到达才做独立验收；验收前不启用生产profile、不宣称准确率提升、不授权PLC。
