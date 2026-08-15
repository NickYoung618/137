# Tasks: Mac 2200 泛化退化诊断

**Input**: `spec.md`、`research.md`、`plan.md`、`analysis.md`

**Current scope**: 只完成纯诊断文档；测试和实现任务保持未开始。

## Phase 1 - Evidence intake and cohort control

- [x] T001 核验 `3ee4b4f` clean worktree、`origin/main` 和唯一孔2仓库
- [x] T002 计算三份外置JSON SHA-256并冻结baseline/candidate commit
- [x] T003 分别复算 `normal=2000` 与 `defective=200`，禁止使用overall做normal验收
- [x] T004 核验两个版本 execution errors均为0且运行时未读取目标真值

## Phase 2 - Root-cause diagnosis

- [x] T005 [US1] 复算normal registration/7/Phi valid、lost、gained与净变化
- [x] T006 [US2] 对照 `_phi_radius_search_pass`、`_refine_phi_reference_phase` 和最终Phi门，确认phase/legacy分数语义错配
- [x] T007 [US2] 统计105张phase lost的序号簇、source、phaseFallback、radius ratio、残差、点数、极性支持和覆盖
- [x] T008 [US3] 对照 `79aa6a4`、`526c080`、`3ee4b4f`，定位geometry硬拒绝历史
- [x] T009 [US3] 区分36张geometry rejected与其中30张old-valid→new-invalid，标记为未经标注证实的比例离群
- [x] T010 [US1] 分解尺寸7的136张lost，确认105上游Phi、30 geometry、1自身切线
- [x] T011 独立记录defective观察，不把其增益计入normal接受

## Phase 3 - SpecKit diagnosis artifacts

- [x] T012 编写 `specs/012-mac-2200-generalization-diagnosis/spec.md`
- [x] T013 编写 `specs/012-mac-2200-generalization-diagnosis/research.md`
- [x] T014 编写 `specs/012-mac-2200-generalization-diagnosis/plan.md`
- [x] T015 编写 `specs/012-mac-2200-generalization-diagnosis/tasks.md`
- [x] T016 编写 `specs/012-mac-2200-generalization-diagnosis/analysis.md`
- [x] T017 给出A1/B1/C1候选、风险和测试矩阵，但不修改运行时

## Phase 4 - Diagnosis delivery gate

- [x] T018 执行 `git diff --check` 并确认只有012 Markdown新增
- [x] T019 提交并推送纯诊断文档到 `origin/main`
- [x] T020 推送后确认worktree clean并停止等待实现授权

## Phase 5 - Test-first implementation (blocked pending explicit approval)

- [ ] T021 [US2] 先增加phase与legacy score contract分离红灯测试
- [ ] T022 [US2] 增加错误极性、低覆盖、高残差、少点、越界不误恢复测试
- [ ] T023 [US3] 先增加geometry诊断与硬拒绝独立证据红灯测试
- [ ] T024 [US1] 增加D7上游score耦合与paired contour自身失败区分测试
- [ ] T025 锁定最新唯一真值E2E `7<=2 px`、`Phi<=1 px`
- [ ] T026 实现A1 score contract分离，保持legacy 0.35不变
- [ ] T027 实现B1 geometry多证据/诊断解耦，不直接放宽0.08
- [ ] T028 只在A1/B1仍有证据支持时评估C1 Phi几何hint与测量有效性分离
- [ ] T029 外置shadow复跑105/36/1/23分层和9帧控制
- [ ] T030 运行unittest、compileall、Schema、SpecKit analyze和Git大文件门
- [ ] T031 Mac严格分组复跑normal 2000与defective 200，并核验最终接受门

## Dependencies and stop condition

- T018依赖T001–T017；T019依赖T018；T020依赖T019。
- T021–T031全部依赖新的明确实现授权，本次不得开始。
- 当前提交完成T020后停止，不得把诊断结论直接改成运行时行为。
