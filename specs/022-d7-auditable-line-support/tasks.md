# Tasks: D7可审核直边支持

## Phase 1: Setup and evidence baseline

- [x] T001 核验HEAD、工作树、唯一权威参考和外置581/582/981证据，记录到`specs/022-d7-auditable-line-support/research.md`
- [x] T002 完成`specs/022-d7-auditable-line-support/spec.md`与`checklists/requirements.md`
- [x] T003 完成`plan.md`、`research.md`、`data-model.md`、`contracts/d7-audit-geometry.md`和`quickstart.md`
- [x] T004 运行SpecKit prerequisites并只读分析`specs/022-d7-auditable-line-support/spec.md`、`plan.md`、`tasks.md`覆盖关系

## Phase 2: User Story 1 - 正式直边支持范围 (P1)

**Goal**: 正式A/B仍是原测量直线，但显示更长的真实窄颈方向支持段且不穿圆弧。

**Independent Test**: 合成圆弧连接+直颈图中，端点共线、处于paired支持投影范围、只朝窄颈方向。

- [x] T005 [US1] 在`tests/test_current_capture_registration.py`新增向外支持裁剪、无证据停止、端点共线和数值不变红灯测试
- [x] T006 [US1] 真实581/582验证更远paired不足且单梯度层不等价，拒绝无证据扩充并记录到research
- [x] T007 [US1] 在`algorithms/hole_2/current_capture.py`实现公法线向窄颈方向裁剪和支持投影有限线段
- [x] T008 [US1] 运行`tests.test_current_capture_registration`并修复正式D7证据测试

## Phase 3: User Story 2 - v6真实REVIEW证据 (P1)

**Goal**: 010可看到v6实际点线，但证据状态不升级且失败不伪造。

**Independent Test**: v6通过夹具输出review-only A/B；v6失败/缺侧夹具不输出；正式boundaries保持空。

- [x] T009 [US2] 在`tests/test_current_capture_registration.py`和`tests/test_current_capture_contract.py`新增v6证据重放、交点一致性、REVIEW隔离和失败保护红灯测试
- [x] T010 [US2] 在`algorithms/hole_2/current_capture.py`用冻结核心函数和v6最终变换重放两侧raw/inlier points、直线和有限支持段
- [x] T011 [US2] 在`algorithms/hole_2/current_capture.py`接线独立legacy review对象并保持evidence unavailable，审计`algorithms/hole_2/main.py`SHA不变
- [x] T012 [US2] 运行`tests/test_current_capture_registration.py`与`tests/test_current_capture_contract.py`并确认010条件保留语义

## Phase 4: User Story 3 - 可视交付与非回归 (P1)

**Goal**: 预览/LabelMe清楚区分正式A/B、公法线和v6 REVIEW，测量结果不变。

**Independent Test**: LabelMe标签/flags和预览颜色符合契约；同输入前后D7/Phi数值与状态一致。

- [x] T013 [US3] 在`tests/test_hole2_batch_report.py`和`tests/test_hole2_batch_review.py`新增正式/REVIEW形状、原坐标、局部放大和无伪造测试
- [x] T014 [US3] 在`tools/render_hole2_batch_report.py`实现正式与REVIEW预览/LabelMe分层和D7局部放大
- [x] T015 [US3] 在`tools/render_hole2_batch_changes.py`同步新旧审核分层
- [x] T016 [US3] 运行`tests/test_hole2_batch_report.py`、`tests/test_hole2_batch_review.py`并检查仓库外022小样

## Phase 5: External validation

- [x] T017 用`scripts/run_hole2_single_acceptance.sh`和唯一权威真值运行单图验收，确认D7<=2px、Phi<=1px
- [x] T018 用`tools/render_hole2_batch_report.py`对010代表帧181及030/050代表帧581/582/981生成仓库外审核图并逐项核验
- [x] T019 用`tools/batch_current_capture.py`对5组100帧运行batch，逐帧比较execution/registration/D7/Phi状态和数值
- [x] T020 用`tools/analyze_hole2_single_truth_study.py`计算5组D7/Phi重复性并确认本轮证据改动不改变基线

## Phase 6: Gates and delivery

- [x] T021 运行`tests/`全套unittest、`algorithms/ tools/ tests/` compileall和`specs/` JSON Schema验证
- [x] T022 运行最终SpecKit prerequisites/analyze并更新`specs/022-d7-auditable-line-support/analysis.md`
- [x] T023 运行`git diff --check`、配置/门限/Phi差异、旧模板、大文件和运行产物审计
- [x] T024 更新全部SpecKit 022任务为完成，提交并正常push `origin/main`

## Dependencies

- T005--T008依赖T001--T004。
- T009--T012依赖T008，避免混淆正式和legacy证据。
- T013--T016依赖T011。
- T017--T024依赖全部实现和定向测试通过。

## MVP

T001--T016交付直边证据语义闭环；T017--T024是提交前强制验收，不能跳过。
