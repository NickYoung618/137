# Tasks: D7边缘层一致性

## Phase 1 - Specify and diagnosis

- [x] T001 确认`2341ba482473ceea5db35a64015a8eb9dd819525` / `main` / clean
- [x] T002 冻结581/582人工距离的离线证据边界和禁止项
- [x] T003 从030组JSONL提取581/582 primary/multiband逐阶段证据
- [x] T004 完成`spec.md`、`research.md`、`analysis.md`和需求质量检查
- [x] T005 完成`plan.md`、`data-model.md`、质量契约和`quickstart.md`

## Phase 2 - Tests first

- [x] T006 [US1] 在`tests/test_current_capture_registration.py`新增少数干扰层下成对主导层稳健恢复红灯测试
- [x] T007 [US1] 新增对等歧义层/支持不足/原门不通过时不误恢复测试
- [x] T008 [US2] 新增初次已成功帧逐值不变与恢复诊断字段契约测试
- [x] T009 [US2] 运行定向测试并确认未实现前按预期失败

## Phase 3 - Minimal implementation

- [x] T010 [US1] 在`algorithms/hole_2/current_capture.py`实现仅失败后的paired-transition稳健层拟合
- [x] T011 [US1] 使最终候选重新经过未修改的支持数/残差/方向/平行度门
- [x] T012 [US2] 输出层恢复尝试/使用、原始/采信点数和初始失败阶段诊断
- [x] T013 [US1] 阻止单梯度multiband以不同物理语义直接输出有效D7

## Phase 4 - External validation

- [x] T014 仓库外复测581/582：581原路径/逐值不变，582不再输出317px单梯度层
- [x] T015 仓库外重跑030组20张，报告D7路径、双峰、静态重复性和Phi逐值差
- [x] T016 重跑9帧development/diagnostic，确认注册/Phi不退化且失败不伪恢复
- [x] T017 权威同图D7≤2px、Phi≤1px，不读取目标标注作为运行时输入

## Phase 5 - Gates and documentation

- [x] T018 运行全套unittest、compileall和所有JSON Schema
- [x] T019 运行SpecKit prerequisites/analyze，消除critical/high缺口
- [x] T020 运行`git diff --check`、门限/配置/Phi diff、大文件和运行产物审计
- [x] T021 更新`analysis.md`、`tasks.md`与最终验证结论
