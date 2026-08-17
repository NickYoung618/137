# Tasks: 单拍视觉分层根因诊断

- [x] T001 创建024规格、计划、研究、契约与任务
- [x] T002 只读抽取145/147/141/161/441/281/261/401/374关键阶段证据
- [x] T003 新增确定性显式子集工具和测试 tools/build_slot_pose_representative_subset.py、tests/test_slot_pose_representative_subset.py，并在Git外构建9张代表manifest/result子集
- [x] T004 用现有review renderer生成每图叠加、联系表、review JSON和CSV
- [x] T005 只读核对yyh/gyj圆拟合、外缘射线、边缘/轮廓可复用实现
- [x] T006 形成逐图根因矩阵和“可修复/需人工”裁决
- [x] T007 运行Schema/diff/污染门，提交并推送024功能分支，不合main、不碰PLC
- [x] T008 [US3] 在 tests/test_legacy_adapter.py 和 tests/test_slot_pose_contract.py 先增加 bundled source、错SHA及无gyj路径回归
- [x] T009 [US3] 在 algorithms/slot_pose/legacy_adapter.py 和 algorithms/slot_pose/contract.py 实现唯一本地核心模块加载及向后兼容
- [x] T010 [US3] 更新 contracts/slot-pose-config.schema.json、config/inspection.example.json 和 config/README.md 的可移植源码合约
- [x] T011 [US3] 证明本地源模式不改视觉函数库存和145/147小样本结果，记录外部参考资产仍需部署供应
