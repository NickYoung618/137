# Tasks: 现拍样品姿态注册与孔2尺寸检测

**Input**: Design documents from `specs/002-current-capture-registration/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: 本功能按 Constitution 和用户要求执行测试先行；每个故事先建立失败测试，再实现。

**Organization**: 按用户故事组织，任务描述显式引用 FR/SC 并给出文件路径。

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 冻结配置、来源和仓库资产边界。

- [x] T001 建立版本化注册/测量质量配置并覆盖 FR-002/FR-006/FR-016 in `config/current_capture_registration.v1.json`
- [x] T002 [P] 记录 v6 与旧参考资产来源、双 CLI 真值隔离边界 in `algorithms/hole_2/README.md`
- [x] T003 [P] 验证图片、私有标注、JSONL、输出和大文件忽略规则 in `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 建立可复用数据结构、哈希、坐标和最小 v6 接口扩展。

- [x] T004 先补相似变换闭环、配置校验和无效值安全失败测试（FR-003/FR-006/FR-008）in `tests/test_current_capture_registration.py`
- [x] T005 在不改变默认行为的前提下为 v6 `extract_image` 增加可选外部姿态种子（FR-001/FR-009）in `algorithms/hole_2/main.py`
- [x] T006 实现配置/候选/支持/注册结果数据结构及 SHA-256 工具（FR-005/FR-015）in `algorithms/hole_2/current_capture.py`
- [x] T007 实现参考/目标相似变换和 JSON 安全数值序列化（FR-003/FR-011）in `algorithms/hole_2/current_capture.py`

**Checkpoint**: 旧 v6 回归不变，新适配层可表达安全失败和可逆映射。

---

## Phase 3: User Story 1 - 可信注册现拍样品 (Priority: P1) 🎯 MVP

**Goal**: 不读取现拍标注，从四个方向中选择得到多特征几何支持的姿态并拒绝假匹配。

**Independent Test**: 合成参考经四方向、尺度、小角度和平移后均恢复正确姿态；强背景单峰和少于三个支持组样例被拒绝。

### Tests for User Story 1

- [x] T008 [P] [US1] 先写四方向、尺度/小角度/平移恢复红灯测试（FR-002/FR-003/SC-001/SC-002）in `tests/test_current_capture_registration.py`
- [x] T009 [P] [US1] 先写强背景单峰、双锚点、候选歧义和残差超限红灯测试（FR-004/FR-006/SC-003）in `tests/test_current_capture_registration.py`

### Implementation for User Story 1

- [x] T010 [US1] 实现参考圆/圆弧空间聚类和主同心圆全局中心/尺度候选（FR-004）in `algorithms/hole_2/current_capture.py`
- [x] T011 [US1] 实现 0/90/180/270 分组局部边缘峰与显著性评分（FR-002/FR-004/FR-005）in `algorithms/hole_2/current_capture.py`
- [x] T012 [US1] 实现稳健相似变换精配准、空间覆盖、残差和候选间隔门禁（FR-003/FR-006/FR-008）in `algorithms/hole_2/current_capture.py`

**Checkpoint**: US1 可独立输出有效姿态或明确拒绝原因，不产生尺寸。

---

## Phase 4: User Story 2 - 输出孔2尺寸与目标坐标映射 (Priority: P2)

**Goal**: 将有效姿态接入 v6，输出两个确认尺寸的参考/目标几何和独立质量状态。

**Independent Test**: 合成几何中旧业务列保留，目标坐标与映射一致；注册或单特征失败时没有伪造值。

### Tests for User Story 2

- [x] T013 [P] [US2] 先写旧业务列、目标 `7` 端点、`Φ12.2` 圆/支撑点和部分失败红灯测试（FR-007/FR-009/FR-010）in `tests/test_current_capture_contract.py`
- [x] T014 [P] [US2] 先写结果 JSON Schema、运行时输入角色和非有限数拒绝红灯测试（FR-011/FR-012/FR-015）in `tests/test_current_capture_contract.py`

### Implementation for User Story 2

- [x] T015 [US2] 用有效注册种子调用 v6 双边界/圆弧检测并保留原始诊断（FR-001/FR-007）in `algorithms/hole_2/current_capture.py`
- [x] T016 [US2] 实现 `7` 双坐标输出和 `Φ12.2` 独立现拍候选质量保护（FR-007/FR-009/FR-010）in `algorithms/hole_2/current_capture.py`
- [x] T017 [US2] 实现不接受目标标注参数的单图检测 CLI 与 JSON 输出（FR-012/FR-015/FR-018）in `tools/run_current_capture.py`
- [x] T018 [US2] 对齐并验证检测结果契约（FR-011/FR-015）in `specs/002-current-capture-registration/contracts/current-capture-result-v1.schema.json`

**Checkpoint**: US1 与 US2 可在不知道现拍真值的情况下完整运行。

---

## Phase 5: User Story 3 - 外置真值离线验收 (Priority: P3)

**Goal**: 严格校验负责人确认资产并计算目标坐标真实误差，不产生生产判定。

**Independent Test**: 临时结果与合成 LabelMe 可得到无序端点和圆误差；哈希、标签、类型、点数或运行时真值泄漏任一错误均拒绝。

### Tests for User Story 3

- [x] T019 [P] [US3] 先写哈希、标签、shape_type、2/77 点和真值泄漏拒绝红灯测试（FR-012/FR-013/SC-003）in `tests/test_current_capture_acceptance.py`
- [x] T020 [P] [US3] 先写 `7` 无序端点/长度与 `Φ12.2` 圆拟合误差红灯测试（FR-014）in `tests/test_current_capture_acceptance.py`

### Implementation for User Story 3

- [x] T021 [US3] 实现严格外置 LabelMe 验证和像素误差计算（FR-013/FR-014）in `tools/evaluate_current_capture.py`
- [x] T022 [US3] 实现验收 CLI、证据范围声明和验收契约（FR-015/FR-017/FR-018）in `tools/evaluate_current_capture.py` and `specs/002-current-capture-registration/contracts/current-capture-acceptance-v1.schema.json`

**Checkpoint**: 真值只在检测结果冻结后由独立工具读取，单图误差完整可审计。

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 全量回归、真实单图、文档与资产门禁。

- [x] T023 [P] 更新服务器/Mac 双阶段命令与限制说明（FR-018）in `README.md` and `specs/002-current-capture-registration/quickstart.md`
- [x] T024 运行全套 unittest、compileall、JSON 语法/契约和旧参考冒烟（SC-004）并记录于 `specs/002-current-capture-registration/tasks.md`
- [x] T025 用外置负责人确认图片执行无真值检测，再单独执行真值验收并如实记录单图指标（SC-005）in `specs/002-current-capture-registration/tasks.md`
- [x] T026 运行 SpecKit analyze、Git 图片/JSONL/大文件门禁及 SHA 审计（SC-006）并记录于 `specs/002-current-capture-registration/tasks.md`

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 → US2 → US3 → Phase 6。
- T004 必须先于 T005-T007；T008-T009 必须先于 T010-T012；T013-T014 必须先于 T015-T018；T019-T020 必须先于 T021-T022。
- US2 依赖 US1 的有效姿态；US3 只依赖冻结的 US2 结果文件，不进入 US1/US2 运行时。

## Parallel Opportunities

- T002/T003、T008/T009、T013/T014、T019/T020 分别修改不同关注面，可并行准备。
- T023 可在核心测试通过后与门禁脚本准备并行；真实单图 T025 必须等待所有实现和契约测试完成。

## Implementation Strategy

1. 先交付 US1：能可信注册或拒绝，不测尺寸。
2. 接入 v6 完成 US2，确保旧列和目标坐标并存。
3. 最后实现 US3，保持真值输入的单向隔离。
4. 冻结配置后只执行一次负责人确认单图验收；不得依据验收 JSON 反向改变候选或门限。

## Execution Evidence

- 实现前 analyze：24/24 FR+SC 有任务覆盖，26/26 任务格式通过，0 个关键问题。
- 自动化测试：23/23 通过，包含外置真实单图 E2E；旧参考冒烟使用默认 `anchors=9,translation+scale+expanded`，`7=447.7198 px`、`Φ12.2=823.8526 px`。
- 外置单图最终检测：`270°`，6 支持，覆盖率 1.0；`7=317.5631 px`，`Φ12.2=539.1520 px`，总耗时 `10275.41 ms`。
- 外置单图验收：`7` 长度/端点平均误差 `1.5631/2.3096 px`；`Φ12.2` 直径/圆心误差 `0.1372/0.5013 px`。首次验收曾如实发现 `7` 端点平均误差 `33.0369 px`，随后依据旧参考切线关系而非真值坐标修正。
- 最终门禁：23/23 `unittest` 通过（包含真实外置 E2E）；`compileall` 通过；12 个仓库 JSON 可解析，配置/检测/验收/批量契约通过；旧参考冒烟结果与上述一致。
- 最终 SpecKit analyze：31/31 FR+SC 覆盖，33/33 任务格式与顺序通过，无待澄清项或占位符。
- Git 资产与大文件审计：73 个已跟踪/候选文件中图片、压缩包和 JSONL 为 0，超过 1 MiB 文件为 0；002 范围行尾空白为 0。外置真值资产、旧参考资产和代码/配置 SHA-256 均与冻结记录一致。
- 外置批量入口一图冒烟：`total=1`、`registrationValid=1`、`technicalComplete=1`、方向 `270=1`；输出 JSONL/汇总均在 `/tmp`，不代表 Mac 2200 张结果。

---

## Phase 7: Audit completeness and Mac batch increment

- [x] T027 先增加错误锚点拒绝、显式逆变换、统一验收汇总和批量统计红灯测试（FR-019/FR-020/FR-021）in `tests/`
- [x] T028 实现结果正/逆变换、坐标系和技术质量状态，任一失败安全返回非零（FR-003/FR-011/FR-020）in `algorithms/hole_2/current_capture.py` and `tools/run_current_capture.py`
- [x] T029 扩展离线验收契约，在同一报告汇总版本/耗时、方向/变换、候选拒绝及特征质量和真实误差（FR-015/FR-019）in `tools/evaluate_current_capture.py` and `contracts/`
- [x] T030 实现不读目标标注的 Mac 外置分组批量回归工具与质量统计（FR-021/SC-008）in `tools/batch_current_capture.py`
- [x] T031 以外置 SHA 锁定的负责人确认单图运行无真值检测后的 E2E LabelMe 验收测试（FR-022/SC-007）in `tests/test_current_capture_real_e2e.py`
- [x] T032 更新 Schema、SpecKit analyze 与 Mac `normal=2000`/`defective=200` 外置回归命令（FR-019/FR-021/SC-008）in `README.md` and `specs/002-current-capture-registration/`
- [x] T033 按上一轮当时的远端限制运行全套单测、真实 E2E、旧参考冒烟、compile/Schema/SHA/资产审计并停在推送前（历史证据）

当时的远端安全证据：`origin=https://github.com/NickYoung618/137.git`，HEAD 为
`033873fcfcdf40c670bf7d7ebc87603c37d03d05`；当时按该轮约束停在推送前。本增量已获得向该唯一远端推送的新授权。

---

## Phase 8: Controlled measurement hardening and delivery

- [x] T034 先增加 `Φ12.2` 主下界饱和触发、非下界不触发、扩展再饱和不误恢复红灯测试（FR-023/FR-024/SC-010）in `tests/test_current_capture_registration.py`
- [x] T035 实现不越界的 `0.88` 主搜索与仅下界饱和触发的 `0.84` 恢复搜索，记录通道和失败保护（FR-023/FR-024）in `algorithms/hole_2/current_capture.py` and `config/current_capture_registration.v1.json`
- [x] T036 先增加 v6 原质量合格回退与不合格/非有限结果拒绝测试，再实现尺寸7受控回退（FR-025/SC-010）in `algorithms/hole_2/current_capture.py` and `tests/test_current_capture_registration.py`
- [x] T037 将负责人确认单图门更新为尺寸7长度误差 `≤2 px`、`Φ12.2` 直径误差 `≤1 px`（FR-026/SC-011）in `tests/test_current_capture_real_e2e.py`
- [x] T038 更新 spec/plan/research/data-model/quickstart 与配置说明，明确触发、字段、回退和外置数据边界（FR-023–FR-026）in `specs/002-current-capture-registration/` and `config/README.md`
- [x] T039 运行全套 unittest、compileall、外置单图 E2E、旧参考冒烟、SpecKit analyze 和 Git 资产/大文件门禁（SC-004/SC-006/SC-010/SC-011）
- [x] T040 核对 diff 和唯一 origin，fetch/rebase 保留远端竞争改动后提交并推送 `main`（SC-009）

Phase 8 推送前证据：rebase 保留远端 A 端面历史后，合并仓库 86/86
`unittest` 通过（其中 7 项显式 Schema gate 用例在默认环境 skip）；临时安装
`jsonschema` 的独立门禁 13/13 通过，且全部 schema 元验证与孔2外置结果/验收契约通过。
`compileall`、旧参考冒烟和 Git 资产门禁通过。SpecKit analyze 为 26/26 FR、
11/11 SC 均有任务覆盖，40/40 任务完成。
外置单图方向 `270°`、技术状态完整；尺寸7长度误差 `1.5631 px`，
`Φ12.2` 直径误差 `0.1372 px`。该图主半径比 `0.9000`，未触发扩展搜索；
扩展触发和失败保护由独立单测验证。
