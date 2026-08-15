# Tasks: 单一真值与无标注重复性诊断

## Phase 1 - Specify / clarify / plan

- [x] T001 确认HEAD=`eb28b1e`、origin/main一致且工作树clean
- [x] T002 明确只有一张人工真值且不再要求追加标注
- [x] T003 建立014 spec/research/plan/tasks/quickstart/analysis
- [x] T004 审计现有重复性与batch诊断工具，定位显式组失败段缺口

## Phase 2 - Test first

- [x] T005 显式采集组不得跨组拼接连续失败段红灯测试
- [x] T006 manifest缺失/重复/未映射严格失败测试
- [x] T007 population/role严格隔离与静态重复性（标准差/6σ/range/MAD）测试
- [x] T008 唯一真值FAIL不得被无标注结果覆盖测试
- [x] T009 工作树输出拒绝测试

## Phase 3 - Implement

- [x] T010 修复`analyze_hole2_batch.py`显式组失败段
- [x] T011 实现可重复JSONL与严格manifest映射
- [x] T012 实现单图验收报告只读摘要
- [x] T013 实现cohort、captureGroup静态重复性、source/recovery/failure统计
- [x] T014 实现诊断边界和外置输出门禁

## Phase 4 - Verify

- [x] T015 用外置开发、固定对照、困难帧和defective生成服务器报告
- [x] T016 保持holdout封存并记录重复性证据限制
- [x] T017 全套unittest、compileall、SpecKit analyze、diff与大文件审计
- [x] T018 更新analysis并完成提交前审计（仅在全部门禁通过后）
- [x] T019 增加显式有序group-size与population/role映射，避免手写2200条manifest
