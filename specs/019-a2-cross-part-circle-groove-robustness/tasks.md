# Tasks: A2 跨零件圆与真槽鲁棒性

**Input**: specs/019-a2-cross-part-circle-groove-robustness/

**Tests**: 本功能按用户要求采用TDD；每个实现任务前有对应失败测试。

## Phase 1: Setup

- [X] T001 记录Constitution误覆盖恢复、当前分支和历史七组只读基线到 specs/019-a2-cross-part-circle-groove-robustness/evidence.md
- [X] T002 [P] 新增不含现场路径的根因家族模板 config/a2-robustness-parts.template.csv

---

## Phase 2: Foundational

- [X] T003 [P] 为两类实验配置的默认关闭、严格数值校验和错误组合先写失败测试到 tests/test_slot_pose_contract.py
- [X] T004 在 algorithms/slot_pose/contract.py、algorithms/slot_pose/angular_profile.py 和 algorithms/slot_pose/physical_outer_circle.py 定义并合并版本化实验配置默认值
- [X] T005 在 contracts/slot-pose-config.schema.json 和 config/closed-loop-guidance-v3.fragment.json 增加向后兼容的实验配置Schema/显式关闭模板
- [X] T006 [P] 为新增配置Schema和旧配置兼容先写/更新契约测试到 tests/test_slot_pose_contract.py 和 tests/test_slot_pose_cli.py

**Checkpoint**: 旧配置解析为实验关闭，错误配置在检测前失败。

---

## Phase 3: User Story 1 - 分层可解释失败证据 (Priority: P1)

**Goal**: 每张图能区分粗候选、稀疏圆、最终圆、暗区候选和真槽失败。

**Independent Test**: 受控点集和一维剖面无需现场图片即可验证扇区残差、原始阈值和拒绝原因。

- [X] T007 [P] [US1] 先写圆扇区分箱、0°环绕、空扇区null和残差摘要失败测试到 tests/test_physical_outer_circle.py
- [X] T008 [P] [US1] 先写暗区原始阈值越界、run宽度/显著度拒绝原因和默认摘要兼容失败测试到 tests/test_angular_profile.py
- [X] T009 [US1] 在 algorithms/slot_pose/physical_outer_circle.py 实现 physical-circle-sector-evidence/1 并保持默认接受判定不变
- [X] T010 [US1] 在 algorithms/slot_pose/angular_profile.py 重构显式阈值run评估并输出原始阈值可用性与逐run拒绝证据
- [X] T011 [US1] 在 algorithms/slot_pose/full_frame_circle_locator.py 传播稀疏/最终圆扇区证据和缩放后门限余量
- [X] T012 [US1] 在 algorithms/slot_pose/legacy_adapter.py 传播angularProfile和candidateSummary新增诊断且保持旧字段
- [X] T013 [P] [US1] 更新 tests/test_full_frame_circle_locator.py 和 tests/test_single_real_groove.py 覆盖顶层传播、失败角度null与旧路径兼容
- [X] T014 [US1] 更新 contracts/slot-pose-result-v3.schema.json 的可选诊断约束或证明现有扩展点足够，并补 tests/test_slot_pose_contract.py

**Checkpoint**: 不启用实验恢复也能完整解释part-008/009/019/023对应阶段。

---

## Phase 4: User Story 2 - 有上限实验鲁棒模式 (Priority: P1)

**Goal**: 在受控局部污染和宽亮度分布下恢复候选，同时在过量污染或不唯一时安全失败。

**Independent Test**: 已知圆和已知槽的合成样本验证精度、上限、环绕、歧义与默认关闭。

- [X] T015 [P] [US2] 先写局部连续污染圆可恢复、跨0°污染、过量污染、覆盖不足、重拟合位移过大和默认关闭测试到 tests/test_physical_outer_circle.py
- [X] T016 [P] [US2] 先写负MAD阈值分位数恢复、阈值有界、假设上限、跨假设去重、0/多槽fail-closed测试到 tests/test_angular_profile.py 和 tests/test_single_real_groove.py
- [X] T017 [US2] 在 algorithms/slot_pose/physical_outer_circle.py 实现一次受限扇区排除重拟合并重新执行完整质量门
- [X] T018 [US2] 在 algorithms/slot_pose/angular_profile.py 实现 angular-dark-candidate-robustness/1 多假设、逐假设证据和环形去重
- [X] T019 [US2] 在 algorithms/slot_pose/legacy_adapter.py 接入实验暗区模式并确保groove recognition只消费去重候选
- [X] T020 [US2] 在 algorithms/slot_pose/full_frame_circle_locator.py 对稀疏和最终阶段复用同一受限圆策略且不重复全链搜索
- [X] T021 [P] [US2] 补 tests/test_full_frame_circle_locator.py、tests/test_single_real_groove.py 和 tests/test_legacy_adapter.py 的legacy/paired/multi-role/single回归
- [X] T022 [US2] 增加同机默认/实验性能与资源测试或基准脚本到 tests/test_full_frame_circle_locator.py 和 specs/019-a2-cross-part-circle-groove-robustness/evidence.md

**Checkpoint**: 实验模式满足合成精度和安全失败；默认模式无回退。

---

## Phase 5: User Story 3 - 整零件分折与封存防泄漏 (Priority: P2)

**Goal**: 用009分组生成可审计LOPO计划，检测前拒绝part-006和任何跨sample/SHA泄漏。

**Independent Test**: 无图合成CSV/lock验证两折、三折、单sample不足、同sample跨侧和封存SHA更名泄漏。

- [X] T023 [P] [US3] 先写分折、单sample不足、跨purpose和封存sample/SHA拒绝测试到 tests/test_a2_robustness_governance.py
- [X] T024 [P] [US3] 新增 a2-robustness-fold-plan/1 Schema测试到 tests/test_a2_robustness_governance.py
- [X] T025 [US3] 在 tools/plan_a2_robustness_folds.py 实现只消费grouping/root-cause/lock的确定性整sample分折
- [X] T026 [US3] 新增 contracts/a2-robustness-fold-plan.schema.json 并在工具输出前自校验有限值、哈希和交集
- [X] T027 [P] [US3] 先写历史JSONL仅解析目标SHA、sealedRecordsParsed=0、五秒门和状态漏斗测试到 tests/test_a2_robustness_governance.py
- [X] T028 [US3] 在 tools/audit_a2_robustness_groups.py 实现目标七组流式审计、阶段漏斗、门限余量和根因汇总
- [X] T029 [US3] 新增 contracts/a2-robustness-audit.schema.json 并输出 audit.json/groups.csv，固定accuracyEvaluated=false

**Checkpoint**: 分折和历史审计均不读取part-006逐图结果，不能把已暴露数据标成严格test。

---

## Phase 6: User Story 4 - 最小人工标注队列 (Priority: P3)

**Goal**: 生成不预填算法真值、按身份稳定选帧的外置人工复核清单。

**Independent Test**: 打乱输入与改变算法分数不改变队列；队列含所需shape、SHA和authority。

- [X] T030 [P] [US4] 先写身份哈希稳定选帧、输入顺序不变、算法字段不参与和媒体不写Git测试到 tests/test_a2_robustness_governance.py
- [X] T031 [US4] 在 tools/audit_a2_robustness_groups.py 输出 annotation-queue.csv，列出外圆弧、真槽边界、槽壁、槽口端点和阴影shape
- [X] T032 [US4] 在 specs/019-a2-cross-part-circle-groove-robustness/contracts/grouped-validation.md 和 quickstart.md 记录LabelMe人工复核流程及生产真值隔离

**Checkpoint**: 队列可直接交现场标注，但不把任何算法候选称为真值。

---

## Phase 7: Polish & Cross-Cutting

- [X] T033 [P] 更新 README.md、config/README.md 和 contracts/slot-pose-output.md 的实验/生产边界、诊断字段与Mac命令
- [X] T034 运行聚焦测试、全量unittest和全部JSON Schema验证并记录到 specs/019-a2-cross-part-circle-groove-robustness/evidence.md
- [X] T035 对外置历史七组执行只读audit dry-run，确认不解析part-006，并记录脱敏统计和输出哈希到 evidence.md
- [X] T036 执行 git diff --check、JSON解析、大文件/媒体/绝对A2路径/证据污染和工作树审计并记录结果
- [X] T037 复核所有FR/SC、完成Spec Kit converge并补齐遗留任务

---

## Dependencies & Execution Order

- Phase 1和2先完成，阻塞所有用户故事。
- US1先提供可解释证据；US2依赖US1的点集/阈值诊断。
- US3仅依赖Phase 2，可与US1/US2代码工作独立；US4依赖US3审计输出。
- Polish依赖所有目标用户故事。

## Parallel Opportunities

- T003/T006、T007/T008、T015/T016、T023/T024和T027、T030可在不同测试文件并行准备。
- 算法实现修改相同文件时必须顺序执行。
- Schema/CLI治理与算法实现文件独立，但最终集成测试后统一验证。

## Implementation Strategy

1. MVP先完成US1：不改变检测结果但让每层失败可解释。
2. 再完成默认关闭的US2合成鲁棒能力。
3. 完成US3/US4的数据隔离和人工标注闭环。
4. 未获得独立真值前停止在“实验可用、生产激活BLOCKED”，不改默认开关。
