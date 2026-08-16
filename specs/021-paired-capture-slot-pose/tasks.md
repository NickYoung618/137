# Tasks: 双帧配对槽姿态与可复核预标注

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/paired-capture.md`

## Phase 1: Setup

- [x] T001 记录021基线分支、全量测试外部依赖失败与默认关闭边界到 specs/021-paired-capture-slot-pose/evidence.md
- [x] T002 [P] 新增默认关闭示例配置 config/paired-capture-slot-pose.example.json
- [x] T003 [P] 新增manifest/config/result Schema到 contracts/paired-capture-manifest.schema.json、contracts/paired-slot-pose-config.schema.json、contracts/paired-slot-pose-result.schema.json

## Phase 2: Foundational

- [x] T004 先写manifest、角度环绕、参数状态和输出契约测试 tests/test_paired_capture_slot_pose.py
- [x] T005 实现严格模型校验、候选提取与角度工具 algorithms/slot_pose/paired_capture.py
- [x] T006 实现JSONL配对CLI及SHA关联 tools/run_paired_slot_pose.py

## Phase 3: User Story 1 - 两拍候选物理互证 (P1)

**Independent Test**: 正负旋转、环绕、固定阴影不动、真槽31°/328°和多解均由纯候选测试裁决。

- [x] T007 [US1] 在 tests/test_paired_capture_slot_pose.py 添加跨帧一对一、角残差、形状门、候选上限和唯一性TDD
- [x] T008 [US1] 在 algorithms/slot_pose/paired_capture.py 实现归一化、全假设评分和fail-closed唯一选择
- [x] T009 [US1] 在 tools/run_paired_slot_pose.py 输出每帧完整raw/assessment/refinement/source evidence

## Phase 4: User Story 2 - 未确认参数安全联调 (P1)

**Independent Test**: UNCONFIRMED空值或暂定数值均valid=false，诊断可见且guidance/PLC为空。

- [x] T010 [US2] 在 tests/test_paired_capture_slot_pose.py 添加UNCONFIRMED、缺帧、重复身份、SHA错配和实验关闭测试
- [x] T011 [US2] 在 algorithms/slot_pose/paired_capture.py 实现EXPERIMENT_DISABLED、DIAGNOSTIC_ONLY和稳定错误库存
- [x] T012 [US2] 在 tools/run_paired_slot_pose.py 保证manifest/SHA先验校验并提供Mac可复现CLI

## Phase 5: User Story 3 - 遮挡选择和第二拍引导 (P2)

**Independent Test**: 第一帧或第二帧单独usable时均输出第二拍后current angle；均不可用时失败。

- [x] T013 [US3] 在 tests/test_paired_capture_slot_pose.py 添加单帧无遮挡、两帧歧义、旋转误差、85±5死区和方向测试
- [x] T014 [US3] 在 algorithms/slot_pose/paired_capture.py 实现measurementSource、第二拍当前角和闭环guidance
- [x] T015 [US3] 在 contracts/paired-slot-pose-result.schema.json 固化image guidance可用而PLC始终阻断的契约

## Phase 6: User Story 4 - 可复核AUTO_预标注 (P2)

**Independent Test**: 临时图和两版结果生成Git外raw/overlay/contact-sheet/LabelMe，标签明确非真值且SHA错时拒绝。

- [x] T016 [US4] 先写审阅包、标签、颜色、外置路径及SHA失败测试 tests/test_slot_pose_prefill_review.py
- [x] T017 [US4] 实现AUTO_LabelMe、019/020 overlay和三栏联系表 tools/prepare_slot_pose_prefill_review.py
- [x] T018 [US4] 保留132112_4只作外部评估参考并在 specs/021-paired-capture-slot-pose/quickstart.md 记录374/369命令和292跳过

## Phase 7: Polish and Gates

- [x] T019 [P] 更新 README.md 双拍实验与预标注入口，明确默认关闭/不合main/未知参数
- [x] T020 运行聚焦、全量、Schema、CLI、diff、JSON、大文件和绝对路径污染检查
- [x] T021 更新 specs/021-paired-capture-slot-pose/evidence.md、勾选任务并核对Constitution追踪
- [x] T022 本地提交并推送021功能分支，不合并main

## Dependencies

- T001-T003 → T004-T006 → T007-T015。
- T016-T018只依赖既有slot-pose结果契约，可与匹配实现独立验证。
- T019-T022依赖所有用户故事完成。

## Implementation Strategy

MVP先完成manifest+纯匹配+UNCONFIRMED安全状态；随后增加第二拍引导，再增加人工审阅。所有测试先于对应实现，默认关闭贯穿每一阶段。

## Phase 8: Convergence - 简化人工复核图

- [x] T023 先在 tests/test_slot_pose_prefill_review.py 增加RAW/SIMPLIFIED两栏、稳定颜色/标题/图例、原分辨率输出及禁止圆/矩形/raw射线的聚焦测试 per FR-021/FR-026/FR-027/SC-007 (partial)
- [x] T024 在 tools/prepare_slot_pose_prefill_review.py 实现独立简化渲染层，仅画019最终左右壁/端点和020 fixture候选区域或方向，不调用完整调试overlay per FR-021/FR-022/FR-026/FR-027 (contradicts)
- [x] T025 收紧LabelMe预填与review索引，只保留最终两侧壁/端点/fixture候选，所有shape保持AUTO_且human_verified=false并拒绝覆盖人工内容 per FR-022/FR-028 (contradicts)
- [x] T026 更新 contracts/slot-pose-prefill-review.schema.json、specs/021-paired-capture-slot-pose/quickstart.md和README.md，明确020候选不等于valid及374/369准确命令 per FR-021/FR-027/Constitution IV (partial)
- [x] T027 运行聚焦/全量/Schema/CLI/diff/媒体与路径污染门，更新evidence，本地提交并推送021功能分支且不合并main per SC-006/SC-008/SC-009 (partial)
