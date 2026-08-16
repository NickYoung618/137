# Tasks: A2 回放验收与根因加固

**Input**: `specs/008-a2-replay-integrity-hardening/` 下的 spec、plan、research、data-model 与 contracts

**Tests**: 本功能按用户要求采用 TDD；每个故事先提交失败测试，再实现最小修复并运行聚焦回归。

## Phase 1: Setup（只读基线）

**Purpose**: 锁定分支、现有行为和外置证据，不改变验收集或生产阈值。

- [X] T001 记录 `main@5c89563`、当前分支、工作树、700条外置证据指纹及现有测试基线到 `specs/008-a2-replay-integrity-hardening/evidence.md`
- [X] T002 [P] 核对 `.gitignore`、媒体后缀、大文件和绝对现场路径门，确认外置回放与人工真值不会进入 Git

---

## Phase 2: Foundational（共享契约）

**Purpose**: 先建立最终结果权威性、数据语义和有效配置所共用的测试夹具。

- [X] T003 在 `tests/fixtures/` 增加不含现场路径/人工真值的最小 v3 最终结果、质量拒绝、中间几何和 Manifest 夹具
- [X] T004 [P] 在 `tests/test_slot_pose_contract.py` 增加最终状态交叉字段一致性与失败结果空角度/空方向契约测试
- [X] T005 [P] 在 `contracts/slot-pose-result-v3.schema.json` 与 `contracts/slot-pose-config.schema.json` 中预留向后兼容的有效配置和歧义解析字段契约

**Checkpoint**: 共享夹具和契约边界可供所有用户故事复用。

---

## Phase 3: User Story 1 - 权威回放结果（Priority: P1）

**Goal**: 统计、CSV、叠加图和联系表只用顶层最终结果判断是否可执行，中间几何单独展示。

**Independent Test**: 混合有效、早期圆失败、槽失败、质量拒绝但有中间角的夹具，最终计数必须精确且失败方向不得计入 `NONE`。

### Tests for User Story 1

- [X] T006 [P] [US1] 在 `tests/test_slot_pose_review.py` 增加质量拒绝不被报为到位、早期失败规范化、null方向独立计数测试并确认先失败
- [X] T007 [P] [US1] 在 `tests/test_slot_pose_review.py` 增加700项自适应联系表尺寸测试并确认固定三列实现先失败
- [X] T008 [P] [US1] 在 `tests/test_a2_replay_audit.py` 增加最终状态互斥性和故意矛盾记录拒绝测试并确认先失败

### Implementation for User Story 1

- [X] T009 [US1] 修改 `tools/render_slot_pose_review.py`，以顶层 v3 结果构建权威 guidance，保留 `intermediateGuidance` 诊断且不参与最终计数
- [X] T010 [US1] 修改 `tools/summarize_slot_pose_diagnostics.py`，统一最终/中间状态命名、空方向和交叉字段一致性统计
- [X] T011 [US1] 修改 `tools/render_slot_pose_review.py` 的联系表布局，按图数自适应列数并保证 JPEG 尺寸上限内完整包含全部样品
- [X] T012 [US1] 运行 `tests/test_slot_pose_review.py` 和最终结果 Schema 聚焦回归，验证质量拒绝、早期失败及700项布局

**Checkpoint**: US1 可独立复现 491/489/2/209 与 271/218/2/209 的权威口径。

---

## Phase 4: User Story 2 - 显式数据集业务语义（Priority: P1）

**Goal**: 数据类别、产品判定、图像质量和姿态可用性各自显式、可溯源且不依赖目录名猜测。

**Independent Test**: 任意嵌套相对路径由外置语义 CSV 精确覆盖；未知姿态可用性只给条件指标，冲突/逃逸/不完整标签被拒绝。

### Tests for User Story 2

- [X] T013 [P] [US2] 在 `tests/test_data_tools.py` 增加语义 CSV 完整覆盖、未知姿态可用性、冲突规则、额外/缺失路径和路径逃逸测试并确认先失败
- [X] T014 [P] [US2] 在 `tests/test_slot_pose_evaluation.py` 增加目录类条件指标与显式 `poseUsable=false` 权威误引导指标分离测试并确认先失败

### Implementation for User Story 2

- [X] T015 [US2] 修改 `tools/make_manifest.py`，加载逐相对路径外置语义 CSV 并写入独立的 dataset/product/image/pose 字段及 authority/provenance
- [X] T016 [US2] 修改 `tools/validate_dataset.py`，校验语义枚举、覆盖完整性、冲突、authority/provenance 和安全相对路径
- [X] T017 [US2] 修改 `tools/evaluate_slot_pose.py`，将目录类条件误引导率与显式姿态可用性权威指标分开并输出阻塞原因
- [X] T018 [US2] 在 `config/README.md` 与 `README.md` 记录外置语义 CSV 用法及“bad 不等于 pose unusable”的安全边界
- [X] T019 [US2] 运行数据工具和评估聚焦测试，验证任意目录名、未知语义和权威标签三条路径
- [X] T045 [US2] 在 `tests/test_data_tools.py` 增加 development/validation/test/acceptance 的物理样品与源图 lineage 隔离、单标注不得兼任验证/测试、700锁定用途测试
- [X] T046 [US2] 修改 `tools/make_manifest.py` 与 `tools/validate_dataset.py`，显式记录 evaluation purpose、锁定 acceptance 运行策略及独立标注集可用状态

**Checkpoint**: US2 可独立重建500/200类别，同时不会把未确认坏图自动当作姿态负样本。

---

## Phase 5: User Story 3 - 可复现有效配置（Priority: P1）

**Goal**: 区分源文件哈希与运行时展开后的有效配置哈希，并使兼容的省略默认值配置通过契约。

**Independent Test**: 省略默认段和显式写出相同默认值得到相同有效哈希；非法显式值在读图前报精确字段错误。

### Tests for User Story 3

- [X] T020 [P] [US3] 在 `tests/test_slot_pose_contract.py` 增加省略/显式默认等价哈希、源哈希不同、路径无关和非法字段测试并确认先失败
- [X] T021 [P] [US3] 在 `tests/test_slot_pose_contract.py` 增加有效配置物化后通过 Schema、源配置兼容 Schema 和结果携带有效哈希测试并确认先失败

### Implementation for User Story 3

- [X] T022 [US3] 修改 `algorithms/slot_pose/contract.py`，实现完整默认合并、规范化有效身份和稳定 SHA-256，同时排除机器绝对路径
- [X] T023 [US3] 新增 `tools/materialize_slot_pose_config.py`，输出可审计的有效配置/身份/源哈希且不读取图像
- [X] T024 [US3] 调整 `contracts/slot-pose-config.schema.json`，允许源配置省略可默认段，并确保物化结果满足完整约束
- [X] T025 [US3] 修改 `algorithms/slot_pose/legacy_adapter.py` 与 `contracts/slot-pose-result-v3.schema.json`，向后兼容地输出 `effectiveConfigSha256`
- [X] T026 [US3] 运行配置、结果契约和 CLI 聚焦测试，验证跨格式/跨路径稳定性

**Checkpoint**: US3 能回答“实际运行了哪些阈值”，且源配置和有效行为均可追溯。

---

## Phase 6: User Story 4 - 有界物理槽歧义解析（Priority: P2）

**Goal**: 多个粗槽候选仅在恰好一个通过既有槽壁/外圆交点精修时恢复，默认关闭且工作量有硬上限。

**Independent Test**: 受控候选的唯一、零、多个和超限精修幸存者分别得到成功、失败、歧义和超限失败；不得按分数、85°或候选编号选择。

### Tests for User Story 4

- [X] T027 [P] [US4] 新增 `tests/test_groove_resolution.py`，覆盖唯一/零/多个/超限幸存者、拒绝证据保留和输入顺序无关并确认先失败
- [X] T028 [P] [US4] 在 `tests/test_single_real_groove.py` 增加适配器多粗候选唯一精修恢复、默认关闭、0/>1失败及旧单候选兼容测试并确认先失败

### Implementation for User Story 4

- [X] T029 [US4] 新增 `algorithms/slot_pose/groove_resolution.py`，协调既有 refiner 逐候选精修、限制最多3个并返回全部尝试和唯一性结论
- [X] T030 [US4] 修改 `algorithms/slot_pose/contract.py` 与 `contracts/slot-pose-config.schema.json`，增加默认关闭、严格校验的 `ambiguity_resolution` 配置
- [X] T031 [US4] 修改 `algorithms/slot_pose/legacy_adapter.py`，只将唯一精修幸存槽送入单槽姿态计算，0/多/超限保持角度与引导为空
- [X] T032 [US4] 运行槽解析、单槽、legacy、paired 与 multi-role 聚焦回归，确认旧模式和默认配置无回退

**Checkpoint**: US4 提供可解释的可选恢复机制，但不在700张验收集上自动启用或宣称增益。

---

## Phase 7: User Story 5 - 无调参根因审计（Priority: P3）

**Goal**: 仅消费 Manifest 与结果 JSONL，生成阶段漏斗、标签覆盖、重复性资格、阈值余量和最小标注队列。

**Independent Test**: 固定小夹具精确重现分阶段计数；无显式组返回 `NOT_EVALUATED`，有明确同件同条件组才计算环形残差。

### Tests for User Story 5

- [X] T033 [P] [US5] 在 `tests/test_a2_replay_audit.py` 增加阶段漏斗、正常/坏图最终分布、未知姿态语义阻塞和最小标注队列测试并确认先失败
- [X] T034 [P] [US5] 在 `tests/test_a2_replay_audit.py` 增加无显式组 `NOT_EVALUATED`、显式组环形残差及700条性能/有界内存测试

### Implementation for User Story 5

- [X] T035 [US5] 新增 `tools/audit_slot_pose_replay.py`，按图匹配 Manifest/JSONL、校验最终状态、计算分层漏斗与条件/权威指标并禁止读原图
- [X] T036 [US5] 新增 `contracts/slot-pose-replay-audit.schema.json`，约束样本数、最终计数、语义阻塞、重复性资格、标注队列和输入指纹
- [X] T037 [US5] 在审计工具中实现显式组环形残差重复性与 circle/groove/sidewall/bad-reason/pose-usability 最小标注队列
- [X] T038 [US5] 使用锁定700条外置 Manifest/JSONL 只读实跑，将新报告写入仓库外新目录并验证491/489/2/209、271/218/2/209及27/20/60/20
- [X] T039 [US5] 在 `specs/008-a2-replay-integrity-hardening/evidence.md` 写入脱敏计数、输入哈希、耗时、Schema结论和全部BLOCKED，不记录现场绝对路径

**Checkpoint**: US5 能复核已证实根因并形成标注工作单，不自动改变生产阈值。

---

## Phase 8: Dataset Evaluation Governance

**Purpose**: 落实本轮“不要一直跑700张”的纠正，避免测试集泄漏和伪造独立精度。

- [X] T047 在 `tools/audit_slot_pose_replay.py` 中输出 development/validation/test/acceptance 分区覆盖、独立真值可用性和锁定回放原因
- [X] T048 在 `README.md`、`config/README.md` 与 `specs/008-a2-replay-integrity-hardening/quickstart.md` 记录当前数据分层：合成+单人工样本用于开发，700用于锁定回归，独立标注 validation/test 为BLOCKED
- [X] T049 只生成不含图像的 validation/test Manifest 模板与最小现场标注问题，不从文件名、25张重叠副本或700张回放伪造物理分组

---

## Phase 9: Polish & Cross-Cutting Validation

- [X] T040 [P] 更新 `README.md` 与 `specs/008-a2-replay-integrity-hardening/quickstart.md`，给出物化配置、语义 Manifest、权威 review/audit 和可选歧义解析的一键命令
- [X] T041 运行完整 `unittest`、所有 JSON Schema 验证和 quickstart 烟测，记录通过/外部依赖失败
- [X] T042 运行 `git diff --check`、JSON解析、媒体/压缩包/大文件/绝对 Mac 与证据路径污染检查
- [X] T043 执行 Spec Kit 收敛检查，确认所有FR/SC/测试映射完成并将本文件任务逐项标记 `[X]`
- [X] T044 在当前独立分支本地提交实现与规格，报告 commit、测试、外置实跑统计、残余BLOCKED；不 push、不 merge、不改 PLC/上位机

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1/US2/US3（P1）→ US4（P2）→ US5（P3）→ Dataset Governance → Polish。
- US1 的最终结果权威口径是 US5 审计和可视化的前置条件。
- US2 的语义模型是权威误引导率的前置条件，但未知语义不阻塞条件指标。
- US3 与 US2 可独立测试；US4 依赖有效配置合并和 v3 诊断契约。
- 每个用户故事内部严格先测试并确认旧实现失败，再实现和回归。
- T038 只审计已存在 JSONL/Manifest，不重新跑700张图片，不用验收标签调参。
- T045-T049 禁止把当前唯一人工样本同时计入 validation/test，禁止把已看过的700张宣称为未见测试真值。

## Implementation Strategy

1. 先交付 US1，消除验收统计把中间几何当最终动作的安全错误。
2. 再交付 US2/US3，使数据语义和实际运行配置可复现。
3. 以默认关闭方式交付 US4；在独立槽/阴影标注完成前不进入生产配置。
4. 最后用 US5 对锁定700条结果复核根因并输出下一轮最小标注，不宣称新的泛化准确率。
