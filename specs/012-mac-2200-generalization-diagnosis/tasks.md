# Tasks: Mac 2200 泛化退化诊断

**Input**: `spec.md`、`research.md`、`plan.md`、`analysis.md`

**Current scope**: 定向实现与服务器验证已完成；Mac 2200严格分组验收待执行。

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

## Phase 5 - Test-first implementation

- [x] T021 [US2] 先增加phase与legacy score contract分离红灯测试
- [x] T022 [US2] 增加错误极性、低覆盖、高残差、少点、越界不误恢复测试
- [x] T023 [US3] 先增加geometry诊断与硬拒绝独立证据红灯测试
- [x] T024 [US1] 增加D7上游score耦合与paired contour自身失败区分测试
- [x] T025 锁定最新唯一真值E2E `7<=2 px`、`Phi<=1 px`
- [x] T026 实现A1 score contract分离，保持legacy 0.35不变
- [x] T027 实现B1 geometry多证据/诊断解耦，不直接放宽0.08
- [x] T028 评估C1：A1/B1后无服务器证据要求拆分Phi几何hint，故不实现额外运行时路径
- [x] T029 外置9帧shadow复跑并确认500/521/620控制帧状态和数值不变；105/36完整分层待Mac
- [x] T030 运行unittest、compileall、Schema、SpecKit analyze和Git大文件门
- [ ] T031 Mac严格分组复跑normal 2000与defective 200，并核验最终接受门

## Phase 6 - External old/new visual review

- [x] T032 先增加默认状态变化、显式帧和工作树输出拒绝红灯测试
- [x] T033 实现通用old/new batch JSONL匹配与状态变化选择，不读取目标真值
- [x] T034 在仓库外输出红/青PNG叠加图与LabelMe预测JSON，只画尺寸7和Phi
- [x] T035 输出版本、有效状态、失败原因、source/recovery与关键质量字段
- [x] T036 用组名一致的外置9帧结果对控制帧620完成真实工具小样并人工检查
- [x] T037 更新012 quickstart并执行全套测试、静态检查和大文件审计

## Dependencies and stop condition

- T018依赖T001–T017；T019依赖T018；T020依赖T019。
- T021–T030及T032–T037已在明确实施授权后完成；T031依赖Mac外置2200张资产。
- 在T031完成前，只能称为服务器验证通过的候选，不得宣称normal 2000已达标。
