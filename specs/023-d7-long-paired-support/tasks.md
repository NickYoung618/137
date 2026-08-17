# Tasks: D7长范围同语义直边支持

**Input**: `specs/023-d7-long-paired-support/`设计文档

**Prerequisites**: plan.md、spec.md、research.md、data-model.md、contracts/、quickstart.md

**Tests**: 本增量强制测试先行；每个实现故事必须先得到预期红灯。

## Phase 1: Setup and evidence baseline

- [x] T001 核验`main`、HEAD、origin/main和clean工作树，并在`specs/023-d7-long-paired-support/research.md`记录yyh/gyj来源SHA
- [x] T002 核验唯一权威模板、581/582人工诊断、010/030/050代表帧和5组100帧均为Git外置
- [x] T003 完成`specs/023-d7-long-paired-support/spec.md`与`checklists/requirements.md`
- [x] T004 完成`plan.md`、`research.md`、`data-model.md`、`contracts/d7-long-support-contract.md`和`quickstart.md`

## Phase 2: Foundational evidence diagnosis

- [x] T005 以现有`detect_dimension_boundary`诊断581/582/981长范围单梯度相对冻结paired直线的残差，记录到`research.md`
- [x] T006 以移动paired窗口诊断581/582/981逐侧连续支持、间隙和远端孤立簇，记录到`research.md`
- [x] T007 运行SpecKit prerequisites和只读analyze，确认FR/SC/任务100%覆盖且无Constitution冲突

## Phase 3: User Story 1 - 延伸有证据的直边显示 (Priority: P1) MVP

**Goal**: 只在A/B双侧连续同语义paired支持存在时延伸冻结直线的有限审核段。

**Independent Test**: 合成移动窗口双侧连续点使A/B增长，断言直线方程、交点和D7值完全不变。

- [x] T008 [US1] 在`tests/test_current_capture_registration.py`新增双侧连续移动paired支持、投影共线和数值冻结红灯测试
- [x] T009 [US1] 在`algorithms/hole_2/current_capture.py`实现移动paired窗口候选采集和逐窗口诊断
- [x] T010 [US1] 在`algorithms/hole_2/current_capture.py`实现沿程去重、连续走廊和双侧共同启用规则
- [x] T011 [US1] 在`algorithms/hole_2/current_capture.py`生成扩展支持点/跃迁对与冻结直线投影段，不重拟合测量几何
- [x] T012 [US1] 运行`tests.test_current_capture_registration`并确认US1定向测试通过

## Phase 4: User Story 2 - 拒绝错误层和无证据延长 (Priority: P1)

**Goal**: 单梯度偏层、单侧中断、跨间隙孤立簇和竞争层均不得扩展正式A/B。

**Independent Test**: 注入各类错误候选，输出保持022原段并给出稳定停止原因。

- [x] T013 [US2] 在`tests/test_current_capture_registration.py`新增单梯度偏4px、单侧失败、跨间隙远端点和支持不足红灯测试
- [x] T014 [US2] 在`algorithms/hole_2/current_capture.py`实现原3px残差、连续间隔、最小新增簇和双侧失败保护
- [x] T015 [US2] 在`tests/test_current_capture_contract.py`新增supportPoints/transitionPairs/stop diagnostics及v6不升级契约测试
- [x] T016 [US2] 在`algorithms/hole_2/current_capture.py`接线向后兼容输出并保持v6 REVIEW和evidence unavailable
- [x] T017 [US2] 运行registration/contract定向套件并确认全部失败保护通过

## Phase 5: User Story 3 - 审核显示 (Priority: P2)

**Goal**: 审核图和LabelMe清楚显示正式长范围支持来源，且不改变Phi或伪造旧回退。

**Independent Test**: 正式扩展、无扩展和v6 REVIEW三类夹具得到不同flags/颜色/状态，原图坐标不变。

- [x] T018 [US3] 在`tests/test_hole2_batch_report.py`和`tests/test_hole2_batch_review.py`新增支持点、LabelMe flags与REVIEW隔离红灯测试
- [x] T019 [US3] 在`tools/render_hole2_batch_report.py`显示扩展支持点并写入LabelMe审核flags
- [x] T020 [US3] 在`tools/render_hole2_batch_changes.py`同步新旧版本扩展支持审核显示
- [x] T021 [US3] 运行renderer定向测试并检查仓库外181/581/582/981审核小样

## Phase 6: Real validation and delivery

- [x] T022 运行权威单图离线验收，确认D7<=2px、Phi<=1px且检测入口未读取truth
- [x] T023 对581/582/981运行逐侧扩展诊断，确认581/582安全停止、981双侧至少48px
- [x] T024 对5组100帧运行batch并逐帧确认execution/registration/D7/Phi状态和数值相对022不变
- [x] T025 对5个显式20帧组重算D7/Phi静态重复性并生成仓库外新旧审核图
- [x] T026 运行全套unittest、compileall、JSON Schema、SpecKit prerequisites/final analyze和`git diff --check`
- [x] T027 审计冻结核心/配置/Phi/门限、旧模板残留、大文件和运行产物，更新`analysis.md`
- [x] T028 标记023任务完成，提交并正常push `origin/main`，报告SHA与Mac视觉复核路径

## Dependencies & Execution Order

- Phase 1--2先冻结证据和安全边界，T007通过后才可实现。
- US1建立扩展主路径；US2在其上增加强制拒绝；US3只消费前两者输出。
- T022--T028依赖全部定向测试通过。

## Parallel Opportunities

- T015可在T013--T014期间独立编写契约红灯，但同一工作树按测试先行顺序串行执行。
- T018的两个renderer测试文件可独立准备；实现文件T019/T020互不覆盖。
- 真实批次T022和静态文档审计可独立，但提交前统一汇总。

## Implementation Strategy

MVP为T001--T012：证明只有双侧连续paired证据才能安全增长冻结线段。T013--T021闭合失败保护和审核契约；
T022--T028为不可跳过的真实资产、全量门禁和交付阶段。
