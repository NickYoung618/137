# Tasks: 真槽同源性误拒裁决

**Input**: `specs/022-source-consistency-adjudication/`

**Tests**: TDD必须先红后绿；真实回放不得用于改写人工真值或运行时身份规则。

## Phase 1: Specification and contracts

- [x] T001 在`specs/022-source-consistency-adjudication/spec.md`固化洁净正例、混合负例、默认关闭、原门不改和PLC阻断 per FR-001-FR-018
- [x] T002 完成`plan.md`、`research.md`、`data-model.md`、`contracts/runtime-adjudication.md`、`quickstart.md`和checklist per SC-007-SC-010
- [x] T003 执行SpecKit analyze，消除覆盖/一致性/Constitution问题后才开始实现

## Phase 2: Contract-first TDD

- [x] T004 [P] [US3] 在`tests/test_source_consistency_adjudication.py`先写配置与纯裁决红门：精确contrast-only、边界、多失败、缺/非有限证据、原payload不变和P95耗时 per FR-003-FR-007/SC-002/SC-007/SC-008
- [x] T005 [P] [US1] 在`tests/test_single_real_groove.py`先写显式开启后洁净contrast-only继续姿态、关闭不回归和PLC仍null红门 per FR-001/FR-008-FR-010/SC-001/SC-004
- [x] T006 [P] [US2] 在`tests/test_single_real_groove.py`先写part-019式混合结构、遮挡、多失败仍fail-closed红门 per FR-011-FR-012/SC-003/SC-006
- [x] T007 [P] [US3] 在`tests/test_slot_pose_contract.py`先写配置字段/模式/精修依赖、未知字段、非有限值和Schema红门 per FR-015-FR-016

## Phase 3: Runtime adjudication

- [x] T008 [US3] 新增`algorithms/slot_pose/source_consistency_adjudication.py`，实现严格配置合并、决策真值表、原证据深拷贝与审计checks per FR-002-FR-007
- [x] T009 [US3] 更新`contracts/source-consistency-adjudication.schema.json`和`contracts/slot-pose-config.schema.json`，约束配置/输出状态一致性 per FR-006/FR-016/SC-007
- [x] T010 [US1] 在`algorithms/slot_pose/contract.py`接入默认关闭配置，只允许single_real_groove+已启用source consistency+精修v2 per FR-001/FR-015-FR-016
- [x] T011 [US1] 在`algorithms/slot_pose/legacy_adapter.py`保留原source payload并接入effective status；仅`ACCEPTED_OVERRIDE`可继续现有姿态链 per FR-007-FR-010
- [x] T012 [US2] 确保local-second-wall partial、多候选resolution、上游失败和原多失败不被override per FR-011-FR-012
- [x] T013 [US3] 新增`config/source-consistency-adjudication.example.json`，必须`enabled=false`并保留development/PLC边界 per FR-010/FR-018

## Phase 4: Offline audit and real evidence

- [x] T014 [P] [US3] 新增`tools/summarize_source_consistency_adjudication.py`只读JSONL汇总decision、effective、原失败和有效/方向分布，不读人工真值 per FR-006/FR-017
- [x] T015 [US1] 使用Git外现140 BMP三折与实验配置回放，单独报告part-008的override、角度/方向与原证据 per FR-013-FR-014/SC-004-SC-005
- [x] T016 [US2] 确认part-019 20/20仍无有效姿态，其他六组不越过原上游失败，不用无真值结果调参 per FR-011-FR-014/SC-003/SC-006
- [x] T017 [US1] 使用145长弧真值离线复核已释放runtime候选角误差`<=5°`，147继续不输出最终角accuracy per FR-013-FR-014/SC-004-SC-005

## Phase 5: Verification and handoff

- [x] T018 更新`README.md`与`specs/022-source-consistency-adjudication/evidence.md`，明确单图证据、默认关闭、原门不变、main/PLC阻断 per FR-017-FR-018
- [ ] T019 运行聚焦/全量测试、全部Schema、CLI、P95性能、diff/媒体/大文件/绝对路径污染门 per SC-001-SC-010
- [x] T020 本地小步提交并推送`022-source-consistency-adjudication`功能分支，不合main、不改PLC；给出Mac独立BMP回放命令 per SC-009-SC-010

## Dependencies

- T003在任何实现前完成。
- T004-T007先红，T008-T013再实现。
- T015-T017只能在合成/单元/契约测试全绿后运行，且不改门限。
- T020依赖服务器工程门和真实负例保护全部通过。
