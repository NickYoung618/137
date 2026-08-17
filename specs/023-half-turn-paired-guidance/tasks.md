# Tasks: 180°双拍槽姿态初版

## Phase 1: Setup

- [x] T001 固化023 SpecKit文档与默认关闭边界到 specs/023-half-turn-paired-guidance/
- [x] T002 [P] 新增默认关闭配置 config/half-turn-guidance.example.json
- [x] T003 [P] 新增输入/配置/结果Schema到 contracts/half-turn-guidance-*.schema.json

## Phase 2: Foundational

- [x] T004 先写角度、输入严格校验和安全失败测试 tests/test_half_turn_guidance.py
- [x] T005 实现统一模型、180°方向无关换算和引导公式 algorithms/slot_pose/half_turn_guidance.py

## Phase 3: User Story 1 - 单图诊断与调整量 (P1)

- [x] T006 [US1] 增加单图成功、80/90边界、±180、检测失败TDD tests/test_half_turn_guidance.py
- [x] T007 [US1] 实现单图入口和诊断结果 algorithms/slot_pose/half_turn_guidance.py

## Phase 4: User Story 2 - 双图互证与唯一调整量 (P1)

- [x] T008 [US2] 增加两拍/一拍usable、固定阴影、矛盾、多解和环绕TDD tests/test_half_turn_guidance.py
- [x] T009 [US2] 复用021候选提取并实现方向无关半圈匹配 algorithms/slot_pose/half_turn_guidance.py
- [x] T010 [US2] 实现一次性单图/双图CLI tools/run_half_turn_guidance.py

## Phase 5: User Story 3 - 错误定位与安全边界 (P2)

- [x] T011 [US3] 覆盖错误库存、完整候选证据、默认关闭和PLC null tests/test_half_turn_guidance.py
- [x] T012 [US3] 输出验证/引导状态、来源和诊断证据 algorithms/slot_pose/half_turn_guidance.py

## Phase 6: Polish

- [x] T013 更新 README.md 与 specs/023-half-turn-paired-guidance/quickstart.md
- [x] T014 运行聚焦/旧paired/全量/Schema/CLI/diff/污染检查并记录 evidence.md
- [x] T015 勾选任务、本地提交并推送023独立功能分支；不合main、不碰PLC
- [x] T016 用少量非sealed真实单帧结果验证两种输入编排可追溯性；无真实pair时明确缺证据，不旋转图片伪造
- [x] T017 记录Mac对b38ffd2的38/38独立聚焦门、单拍代表判读和真实pair缺失边界到 specs/023-half-turn-paired-guidance/evidence.md；不改算法/阈值/main/PLC

## Dependencies

T001-T003 → T004-T005 → T006-T012 → T013-T015。US1与US2共享角度/结果模型但可分别验收。
