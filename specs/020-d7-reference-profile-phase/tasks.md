# Tasks: D7参考剖面相位候选

## Phase 1: Setup and evidence boundary

- [x] T001 审计当前HEAD、Spec 019未提交改动和外置581/582证据边界，记录到`specs/020-d7-reference-profile-phase/research.md`
- [x] T002 审计yyh/gyj孔2、side_length和B端面可复用方法，记录禁止复制项到`specs/020-d7-reference-profile-phase/research.md`
- [x] T003 完成`spec.md`及`checklists/requirements.md`
- [x] T004 完成`plan.md`、`data-model.md`、`contracts/d7-reference-profile-audit.md`和`quickstart.md`

## Phase 2: Tests first

- [x] T005 [US1] 在`tests/test_d7_reference_profile.py`新增权威相位自匹配和亚像素平移测试
- [x] T006 [US1] 在`tests/test_d7_reference_profile.py`新增更强邻层、错误极性、对等歧义层和低对比度拒绝测试
- [x] T007 [US2] 在`tests/test_d7_reference_profile.py`新增独立候选契约及正式D7不覆盖测试
- [x] T008 [US3] 在`tests/test_d7_reference_profile.py`新增LabelMe D7-A/B逐侧比较与缺标签失败测试
- [x] T009 运行定向测试并记录预期红灯到`specs/020-d7-reference-profile-phase/analysis.md`

## Phase 3: Reference profile candidate

- [x] T010 [US1] 在`algorithms/hole_2/d7_reference_profile.py`实现参考灰度/梯度剖面模型
- [x] T011 [US1] 在`algorithms/hole_2/d7_reference_profile.py`实现多扫描归一化相关、极性和最佳/次佳margin
- [x] T012 [US1] 在`algorithms/hole_2/d7_reference_profile.py`实现跨扫描一致性、亚像素点、稳健直线和公法线距离
- [x] T013 [US2] 在`algorithms/hole_2/d7_reference_profile.py`实现版本化独立审计对象，固定`formalMeasurementUpdated=false`

## Phase 4: Offline diagnostic CLI

- [x] T014 [US3] 在`tools/diagnose_d7_reference_profile.py`实现权威参考、目标图和注册变换输入
- [x] T015 [US3] 在`tools/diagnose_d7_reference_profile.py`实现可选外置LabelMe D7-A/B逐侧比较
- [x] T016 [US2] 确认CLI不写入正式结果、不读取标称值且输出路径可位于仓库外

## Phase 5: External validation

- [x] T017 用权威018e/faf同图验证每侧候选误差不超过2px且正式结果未修改
- [x] T018 对581/582外置图生成无真值候选诊断，禁止利用297.1722/300.0442选择候选
- [x] T019 使用冻结SHA的581/582坐标JSON运行逐侧外峰/中点/内峰/人工相位审核；证据不支持单一相位规则，候选不晋级正式D7
- [x] T020 通过旁路隔离和全套回归确认Spec 019正式路径、9帧契约和Phi不受020候选影响

## Phase 6: Gates and analysis

- [x] T021 运行全套unittest、compileall和JSON Schema
- [x] T022 运行SpecKit prerequisites/analyze并记录覆盖结果
- [x] T023 运行`git diff --check`、旧模板、门限、配置、大文件和运行产物审计
- [x] T024 更新`analysis.md`和任务状态，明确候选是否仍仅诊断

## Dependencies

- T005--T009依赖T001--T004。
- T010--T013必须在相应红灯测试后执行。
- T014--T016依赖T010--T013。
- T019依赖外置坐标JSON，不阻塞与真值无关的T020--T024，但阻塞候选晋级。

## MVP

T001--T024：交付可重复的参考剖面独立候选、坐标级逐层诊断和安全的不晋级结论，不改变正式D7。
