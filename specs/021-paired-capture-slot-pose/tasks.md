# Tasks: 双帧配对槽姿态与可复核预标注

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/paired-capture.md`

## Phase 1: Setup

- [x] T001 记录021基线分支、全量测试外部依赖失败与默认关闭边界到 specs/021-paired-capture-slot-pose/evidence.md
- [x] T002 [P] 新增默认关闭示例配置 config/paired-capture-slot-pose.example.json
- [x] T003 [P] 新增manifest/config/result Schema到 contracts/paired-capture-manifest.schema.json、contracts/paired-slot-pose-config.schema.json、contracts/paired-slot-pose-result.schema.json

## Phase 2: Foundational

- [x] T004 先写manifest、角度环绕、参数状态和输出契约测试 tests/test_paired_capture_slot_pose.py
- [x] T005 实现严格模型校验、候选提取与角度工具 algorithms/slot_pose/paired_capture.py
- [x] T006 实现JSONL配对CLI及SHA关联 tools/run_paired_slot_pose.py

## Phase 3: User Story 1 - 两拍候选物理互证 (P1)

**Independent Test**: 正负旋转、环绕、固定阴影不动、真槽31°/328°和多解均由纯候选测试裁决。

- [x] T007 [US1] 在 tests/test_paired_capture_slot_pose.py 添加跨帧一对一、角残差、形状门、候选上限和唯一性TDD
- [x] T008 [US1] 在 algorithms/slot_pose/paired_capture.py 实现归一化、全假设评分和fail-closed唯一选择
- [x] T009 [US1] 在 tools/run_paired_slot_pose.py 输出每帧完整raw/assessment/refinement/source evidence

## Phase 4: User Story 2 - 未确认参数安全联调 (P1)

**Independent Test**: UNCONFIRMED空值或暂定数值均valid=false，诊断可见且guidance/PLC为空。

- [x] T010 [US2] 在 tests/test_paired_capture_slot_pose.py 添加UNCONFIRMED、缺帧、重复身份、SHA错配和实验关闭测试
- [x] T011 [US2] 在 algorithms/slot_pose/paired_capture.py 实现EXPERIMENT_DISABLED、DIAGNOSTIC_ONLY和稳定错误库存
- [x] T012 [US2] 在 tools/run_paired_slot_pose.py 保证manifest/SHA先验校验并提供Mac可复现CLI

## Phase 5: User Story 3 - 遮挡选择和第二拍引导 (P2)

**Independent Test**: 第一帧或第二帧单独usable时均输出第二拍后current angle；均不可用时失败。

- [x] T013 [US3] 在 tests/test_paired_capture_slot_pose.py 添加单帧无遮挡、两帧歧义、旋转误差、85±5死区和方向测试
- [x] T014 [US3] 在 algorithms/slot_pose/paired_capture.py 实现measurementSource、第二拍当前角和闭环guidance
- [x] T015 [US3] 在 contracts/paired-slot-pose-result.schema.json 固化image guidance可用而PLC始终阻断的契约

## Phase 6: User Story 4 - 可复核AUTO_预标注 (P2)

**Independent Test**: 临时图和两版结果生成Git外raw/overlay/contact-sheet/LabelMe，标签明确非真值且SHA错时拒绝。

- [x] T016 [US4] 先写审阅包、标签、颜色、外置路径及SHA失败测试 tests/test_slot_pose_prefill_review.py
- [x] T017 [US4] 实现AUTO_LabelMe、019/020 overlay和三栏联系表 tools/prepare_slot_pose_prefill_review.py
- [x] T018 [US4] 保留132112_4只作外部评估参考并在 specs/021-paired-capture-slot-pose/quickstart.md 记录374/369命令和292跳过

## Phase 7: Polish and Gates

- [x] T019 [P] 更新 README.md 双拍实验与预标注入口，明确默认关闭/不合main/未知参数
- [x] T020 运行聚焦、全量、Schema、CLI、diff、JSON、大文件和绝对路径污染检查
- [x] T021 更新 specs/021-paired-capture-slot-pose/evidence.md、勾选任务并核对Constitution追踪
- [x] T022 本地提交并推送021功能分支，不合并main

## Dependencies

- T001-T003 → T004-T006 → T007-T015。
- T016-T018只依赖既有slot-pose结果契约，可与匹配实现独立验证。
- T019-T022依赖所有用户故事完成。

## Implementation Strategy

MVP先完成manifest+纯匹配+UNCONFIRMED安全状态；随后增加第二拍引导，再增加人工审阅。所有测试先于对应实现，默认关闭贯穿每一阶段。

## Phase 8: Convergence - 简化人工复核图

- [x] T023 先在 tests/test_slot_pose_prefill_review.py 增加RAW/SIMPLIFIED两栏、稳定颜色/标题/图例、原分辨率输出及禁止圆/矩形/raw射线的聚焦测试 per FR-021/FR-026/FR-027/SC-007 (partial)
- [x] T024 在 tools/prepare_slot_pose_prefill_review.py 实现独立简化渲染层，仅画019最终左右壁/端点和020候选证据，不调用完整调试overlay per FR-021/FR-022/FR-026/FR-027 (superseded by T028-T029 interval semantics)
- [x] T025 收紧LabelMe预填与review索引，只保留最终两侧壁/端点/候选证据，所有shape保持AUTO_且human_verified=false并拒绝覆盖人工内容 per FR-022/FR-028 (superseded by T028-T029 interval semantics)
- [x] T026 更新 contracts/slot-pose-prefill-review.schema.json、specs/021-paired-capture-slot-pose/quickstart.md和README.md，明确020候选不等于valid及374/369准确命令 per FR-021/FR-027/Constitution IV (partial)
- [x] T027 运行聚焦/全量/Schema/CLI/diff/媒体与路径污染门，更新evidence，本地提交并推送021功能分支且不合并main per SC-006/SC-008/SC-009 (partial)

## Phase 9: Convergence - 区间审阅语义与局部第二壁诊断

- [x] T028 [US5] 先在 tests/test_slot_pose_prefill_review.py 覆盖pairEvidence选择、NOT_MATCHED/PAIR_INCOMPLETE、不允许nearest补位、角度括号三刻线与FR-032 flags per FR-029-FR-032/SC-010
- [x] T029 [US5] 修正 tools/prepare_slot_pose_prefill_review.py：fixture身份与raw区间分离，interval linestrip/方向降级及可视声明，不再画polygon/实心区域 per FR-029-FR-032
- [x] T030 [US5] 更新contracts、quickstart、README和证据，记录374/369人工反馈仅为语义负例而非像素真值 per FR-033/BLOCKED-B05
- [x] T031 [US6] 先写 tests/test_local_second_wall.py，覆盖方形槽唯一补齐、fixture跨源、多解、缺边和31°/328° per FR-034-FR-039/SC-011
- [x] T032 [US6] 实现 algorithms/slot_pose/local_second_wall.py 的严格配置、局部侧壁枚举、独立几何/暗开口/剖面门和全假设输出 per FR-034-FR-038
- [x] T033 [US6] 在contract与legacy_adapter增加默认关闭诊断钩子；唯一实验候选不得改变GROOVE_SOURCE_INCONSISTENT、valid或PLC字段 per FR-034/FR-037/SC-012
- [x] T034 更新SpecKit contracts/data-model/quickstart与Mac外置实验配置命令；不修改现有020阈值或默认配置 per FR-020/FR-034
- [x] T035 运行spec analyze、聚焦/全量、Schema/CLI/diff/JSON/媒体/路径污染门，更新evidence并提交推送021分支，不合main per SC-006/SC-008/SC-009
- [x] T036 [US6] 输出CANDIDATE_MISSING/LOCAL_SECOND_WALL_NOT_FOUND/MULTIPLE_LOCAL_OPENINGS/SOURCE_INCONSISTENT阶段码，所有side search候选携带failedChecks per FR-040
- [x] T037 [US6] 在局部假设checks标注geometry/endpoint/opening/source层和hardGate，同一外圆端点残差进入硬门，score不得越门 per FR-041
- [x] T038 [US6] 补任意旋转、环绕、曝光/模糊、fixture对比/宽度不对称及部分重叠的端点/中点误差与fail-closed测试 per FR-042/SC-013
- [x] T039 [US6] 记录Mac 140张021回放与part-019已知负例，不放宽0.12且不称准确率 per FR-033/SC-009
- [x] T040 [US6] 在 tests/test_local_second_wall.py 先覆盖逐seed拒绝阶段、线段、anchor evidence、cluster成员守恒和pre/post hypothesis对账 per FR-043/FR-044/FR-045/FR-046/SC-014
- [x] T041 [US6] 在 algorithms/slot_pose/local_second_wall.py 输出diagnostic/2逐seed、anchor、side/hypothesis merge cluster和吸附摘要，不改变配置/门限/权威状态 per FR-043/FR-044/FR-045/FR-046
- [x] T042 新增 tools/extract_local_second_wall_trace.py 与 tests/test_local_second_wall_trace.py，从JSONL按basename导出无图像/无绝对路径的374/369结构trace per SC-014
- [x] T043 更新Schema、contract、quickstart和README，给Mac二图重跑/trace命令，保持020/双拍默认关闭和PLC阻断 per FR-020/FR-043-FR-046
- [x] T044 运行聚焦/全量/Schema/diff/媒体与路径污染门，更新evidence、提交推送021分支，不合main per SC-006/SC-008/SC-009

## Phase 10: Convergence - 双向/outward局部墙搜索

**Goal**: 修正140张trace证明的“错误粗暗区只向内搜索”结构缺陷，生成可追溯物理墙与无序墙对，仍不提升姿态。

**Independent Test**: 合成槽的真实另一壁分别在start/end外侧及0°/360°边界时能形成外侧cluster；内侧fixture混合对被拒绝，零/多解fail-closed，顶层valid和PLC不变。

- [x] T045 [US6] 用SpecKit更新 specs/021-paired-capture-slot-pose/spec.md、plan.md、research.md、data-model.md、contracts/paired-capture.md和quickstart.md，记录140张missing-before-merge证据与FR-047-FR-055/SC-015-SC-018
- [x] T046 [US6] 先在 tests/test_local_second_wall.py 增加config/2严格校验、start/end inward/outward domain、wrap360、seed/候选上限的失败测试 per FR-047/FR-051/SC-018
- [x] T047 [US6] 先在 tests/test_local_second_wall.py 增加start外侧、end外侧、fixture内侧、无序canonical ID、旧混合对拒绝、多解/零解和31°/328°回归 per FR-048-FR-052/SC-015/SC-016
- [x] T048 [US6] 在 algorithms/slot_pose/local_second_wall.py 实现四个有界wrap360搜索域、双极性独立seed拟合、上限门与逐seed失败证据 per FR-035/FR-047/FR-048/FR-051
- [x] T049 [US6] 在 algorithms/slot_pose/local_second_wall.py 实现全domain physical wall cluster、无序canonical pair、原已拒绝端点对硬拒绝和同一方形开口分层门 per FR-036/FR-049/FR-050/FR-052
- [x] T050 [P] [US6] 升级 contracts/local-second-wall-diagnostic-config.schema.json、contracts/local-second-wall-diagnostic-result.schema.json、config/local-second-wall-diagnostic.example.json和 algorithms/slot_pose/contract.py 的config/2、diagnostic/3契约 per FR-047/FR-051/FR-055
- [x] T051 [P] [US4] 先更新 tests/test_slot_pose_prefill_review.py，再修改 tools/prepare_slot_pose_prefill_review.py 仅画最终双向wall cluster/canonical pair并使用AUTO_experimental_、human_verified=false per FR-022/FR-054
- [x] T052 [P] [US6] 更新 tools/extract_local_second_wall_trace.py、contracts/local-second-wall-trace-export.schema.json与tests/test_local_second_wall_trace.py，脱敏导出domain/cluster/canonical pair并校验成员守恒 per FR-051/SC-016
- [x] T053 [US6] 运行SpecKit analyze后完成聚焦单测、Schema、runtime默认关闭和历史合成回归，修正所有非预期失败 per SC-006/SC-008/SC-015-SC-018
- [x] T054 [US6] 使用Git外a2-validation-140三折回放diagnostic/3，导出374/369简化图、外侧cluster/旧混合对/part-008/上游错误统计且不称准确率 per FR-053/FR-054/SC-017
- [x] T055 更新README/evidence，运行全量、Schema/CLI/diff/JSON/媒体/路径/性能门，提交并推送021分支，不合main、不改PLC per FR-055/SC-006/SC-008/SC-018

### Phase 10 Dependencies

- T045 → T046-T047 → T048-T049。
- T050-T052可在核心结构稳定后按不同文件并行；T053必须在实现和契约同步后执行。
- T054仅使用冻结三折清单且不含part-006；T055依赖所有前置门完成。

## Phase 11: Evidence Correction - 单壁可观测性

**Goal**: 纠正374人工shape的错误label语义，停止把可能被遮挡的相对壁作为单帧必可恢复前提；不改运行时、门限、默认配置、main或PLC。

- [x] T056 [US4] 只读比较人工两点与AUTO 285.953°墙cluster，记录重合指标和“可见真壁”语义，不把shape用作相对壁真值 per FR-057/FR-058
- [x] T057 [US6] 更新spec/plan/research/data-model/evidence，规定单壁观测继续fail-closed、局部Cartesian不得补造隐藏壁、双拍至少一帧无遮挡 per FR-059-FR-061/SC-020
- [x] T058 [US4] 在Mac锁定原人工JSON SHA并生成不覆盖原件的语义派生副本；服务器Git外复核原件、派生副本与压缩包SHA，媒体/JSON不得入Git per FR-056/SC-019

### Phase 11 Dependencies

- T056 → T057；T058由持有原始人工JSON的Mac执行，不依赖算法修改。

## Phase 12: Initial MVP - 部分观测状态与完整槽复核队列

**Goal**: 版本化表达单壁/混合边的非权威partial状态，保护374负例，并从140张中生成不含真值的最小完整槽复核队列。

**Independent Test**: 单墙、混合边、完整双壁、0墙/多解合成契约全部通过；队列对输入顺序稳定、排除显式partial sample且不含角度择样字段。

- [x] T059 [US7] 先在 tests/test_local_second_wall.py 与 tests/test_single_real_groove.py 增加PARTIALLY_OBSERVED、374式混合边不提升、完整双壁valid/85°修正不回退测试 per FR-062-FR-067/SC-021-SC-023
- [x] T060 [P] [US7] 先在 tests/test_complete_groove_review_queue.py 增加manifest/result对账、sample内SHA稳定选帧、partial排除、无真值/路径安全/外置输出测试 per FR-068-FR-070/SC-024
- [x] T061 [US7] 在 algorithms/slot_pose/local_second_wall.py 实现diagnostic/4 PARTIALLY_OBSERVED与partialObservation，保持0.12、0.5°和顶层失败不变 per FR-062-FR-065
- [x] T062 [P] [US7] 更新 contracts/local-second-wall-diagnostic-result.schema.json、algorithms/slot_pose/contract.py、trace exporter和相应契约测试到diagnostic/4 per FR-062-FR-064/SC-025
- [x] T063 [US7] 实现 tools/build_complete_groove_review_queue.py 与 contracts/complete-groove-review-queue.schema.json，按sample证据筛选及SHA选帧 per FR-068-FR-070
- [x] T064 [US7] 更新 README.md、specs/021-paired-capture-slot-pose/quickstart.md和evidence.md，明确partial非真槽身份、Mac队列/回放命令和初版验收边界 per FR-063-FR-070
- [x] T065 [US7] 用服务器Git外140张冻结三折结果生成最小复核队列和review manifest，显式排除part-006及已知partial part-019，只报告候选证据不称准确率 per SC-024
- [x] T066 [US7] 用服务器Git外374原图/结果运行diagnostic/4聚焦回归，确认PARTIALLY_OBSERVED且顶层无角/PLC；不重跑完整140张 per SC-021/SC-022
- [x] T067 运行SpecKit analyze、聚焦/全量测试、全部Schema、CLI、diff/JSON/媒体/绝对路径污染门 per SC-025
- [x] T068 更新任务和脱敏证据，本地提交并推送021功能分支，不合main、不改PLC per SC-025

### Phase 12 Dependencies

- T059-T060先于T061-T063；T061-T063完成后执行T064-T066；T067-T068收尾。
- T065只读取冻结140张外置manifest/JSONL；T066只运行374代表帧，不使用人工标注作为运行时输入。

## Phase 13: Convergence - Mac测试资产跨平台隔离

- [x] T069 为tests/test_manual_groove_pose_review.py和tests/test_slot_pose_batch.py建立临时目录自包含legacy最小资产/配置helper，移除对config/inspection.example.json中服务器绝对路径的直接依赖，并增加服务器专用gyj资产根不存在时仍可运行的回归 per SC-006/SC-008/plan: Target Platform (partial)
- [x] T070 运行聚焦与服务器全量测试、diff/媒体/绝对路径污染门，在evidence记录Mac的390 pass/16 skip/4同根因error及修复后复跑要求，提交并推送021分支且不合main per SC-008/Constitution IV (partial)

## Phase 14: Convergence - macOS符号路径规范化

- [x] T071 修正tests/test_manual_groove_pose_review.py的临时资产包含断言，在比较前对根目录和资产路径同时resolve，并用临时symlink root回归覆盖macOS逻辑临时路径与规范物理路径的等价语义；运行聚焦/全量/污染门、记录证据并推送021，不改helper输出或任何生产路径 per SC-008/plan: Target Platform (partial)

## Phase 15: Completion Audit - 真值前可安全收敛

- [x] T072 [US6] 澄清 specs/021-paired-capture-slot-pose/spec.md 中FR-038与FR-062—FR-065的状态优先级，区分无墙证据与部分墙证据，不改运行时、门限或权威边界 per FR-038/FR-062-FR-065/SC-021
- [x] T073 [P] [US1] 先在 tests/test_paired_capture_slot_pose.py 增加Schema拒绝重复captureIndex、跨平台绝对/逃逸路径和CONFIRMED缺参数测试，再收紧 contracts/paired-capture-manifest.schema.json 与运行时路径一致性 per FR-001-FR-003/FR-017/SC-001
- [x] T074 建立 specs/021-paired-capture-slot-pose/completion-audit.md，对FR-001—FR-070和SC-001—SC-025逐条标记已证实、历史矛盾已纠正、缺真值证据与可安全继续项，不推断part-008 145/147真值 per Constitution I/IV
- [x] T075 运行聚焦/全量/Schema/CLI/diff/媒体/绝对路径污染门，更新 specs/021-paired-capture-slot-pose/evidence.md，提交并推送021功能分支，不读sealed part-006、不调门限、不合main、不碰PLC per SC-008/SC-009/SC-025

## Phase 16: Independent Mac Gate - completion audit

- [x] T076 将Mac对6f12585的六模块、全量、39份Schema、三个CLI与diff独立通过结果记录到 specs/021-paired-capture-slot-pose/evidence.md 和 completion-audit.md；明确预期trace拒绝文本不是失败、无需重跑140 BMP且145/147人工门不变，只提交推送021分支，不合main、不碰PLC per SC-008/SC-009/SC-025

## Phase 17: Human Review - 局部fixture污染定位

**Historical status**: 本阶段在当时语义下完成，但其“槽壁污染”前提已被最终人工澄清A否定。产物只作历史审计，Phase 19负责停用生成路径并更正后续动作。

**Goal**: 原样保存145/147的YES/YES/YES/YES+PARTIAL语义，并生成不自动造HUMAN坐标的最小污染子段标注请求。

**Independent Test**: 临时review-index、raw与AUTO LabelMe按SHA关联；派生AUTO shapes逐点不变，错误身份/哈希/已有人工内容/非PARTIAL响应在写出前拒绝。

- [x] T077 [US8] 更新 specs/021-paired-capture-slot-pose/spec.md、plan.md、research.md、data-model.md和contracts/paired-capture.md，区分真实槽身份确认、端点语义确认、局部fixture污染和像素真值不可用 per FR-071-FR-078/SC-026
- [x] T078 [P] [US8] 先在 tests/test_fixture_contamination_annotation.py 添加精确语义、SHA关联、AUTO shape守恒、零自动HUMAN坐标和失败分支测试 per FR-071-FR-076/SC-026-SC-029
- [x] T079 [P] [US8] 新增 contracts/fixture-contamination-review.schema.json，固化四项回答、PARTIAL污染、UNCONFIRMED重叠状态及所有禁止升权策略 per FR-071-FR-073/FR-076/SC-026
- [x] T080 [US8] 实现 tools/prepare_fixture_contamination_annotation.py，验证review-index/raw/AUTO SHA，Git外逐点派生LabelMe并只声明left/right污染子段标签 per FR-073-FR-075/SC-027-SC-029
- [x] T081 [US8] 更新 specs/021-paired-capture-slot-pose/quickstart.md、completion-audit.md和evidence.md，记录145/147精确语义、Mac命令及后续支持点重叠诊断边界 per FR-077-FR-078/SC-030
- [x] T082 运行SpecKit analyze、聚焦/全量、全部Schema、CLI、diff/媒体/绝对路径/阈值污染门，不读取sealed part-006、不重跑140张 per SC-030
- [x] T083 提交并推送021功能分支，保持main隔离、PLC未授权，等待Mac对新工具及真实外置review bundle独立验证 per SC-030

## Phase 18: Independent Mac Gate - fixture contamination review

- [x] T084 记录Mac对cd7f3ca的3项聚焦、400项全量、16项平台skip以及真实145/147外置派生LabelMe SHA门；确认源图/AUTO未覆盖、四项语义与全部false策略保留，仅提交推送021，不合main、不调门限、不碰PLC per SC-026-SC-030

## Phase 19: Definitive Clarification A - 干净槽壁与旧污染请求停用

**Goal**: 原样保留145/147的A语义，拒绝继续生成槽壁污染子段，并将下一个最小动作改为独立干净槽壁/端点像素复核。

**Independent Test**: 旧CLI使用任意输入均在写出前返回DORMANT/INAPPLICABLE，输出目录不存在；规格和证据不再声称AUTO槽壁受fixture污染。

- [x] T085 [US8] 更新 specs/021-paired-capture-slot-pose/spec.md、plan.md、research.md、data-model.md、contracts/paired-capture.md和quickstart.md，原样记录A、干净槽壁语义、非槽阴影候选不完整与像素真值缺口 per FR-071-FR-078/SC-026/SC-029
- [x] T086 [P] [US8] 先修改 tests/test_fixture_contamination_annotation.py，覆盖函数/CLI全输入停用、零输出以及历史Schema仅可审计语义 per FR-073-FR-074/SC-027-SC-028
- [x] T087 [US8] 将 tools/prepare_fixture_contamination_annotation.py 改为写出前fail-closed的dormant兼容CLI，并在 contracts/fixture-contamination-review.schema.json 声明历史生命周期 per FR-073-FR-074/SC-027-SC-028
- [x] T088 [US8] 更新 specs/021-paired-capture-slot-pose/completion-audit.md、evidence.md、checklists/requirements.md和tasks.md，保留已生成两份外置LabelMe SHA但标为dormant/inapplicable，定义墙支持点+端点的下一步 per SC-026-SC-030
- [x] T089 运行SpecKit analyze、聚焦/全量、40份Schema、CLI拒绝、diff/媒体/绝对路径/算法阈值污染门，不重跑140图、不读sealed part-006 per SC-030
- [x] T090 提交并推送021功能分支，保持main隔离、PLC未授权，等待Mac独立验证 per SC-030

## Phase 20: Independent Mac Gate - definitive clarification A

- [x] T091 记录Mac对c7fdc46的3项聚焦、400项全量、16项平台skip、40份Schema、dormant CLI exit=2/stdout零字节/零输出目录及diff/status门；明确无需重跑140 BMP，仅提交推送021、不合main、不碰PLC per SC-026-SC-030

## Phase 21: Independent clean-groove pixel review

**Goal**: 为145/147生成零AUTO坐标的Git外独立人工任务，并以严格校验分开证明墙/端点复核完成与外圆角度参考可用。

**Independent Test**: 临时review-index/raw/AUTO按SHA关联；准备产物`shapes=[]`且不解析AUTO；完成校验覆盖3+3墙点、2端点、可选圆弧/圆心及所有失败分支。旧污染CLI继续零输出拒绝。

- [x] T092 [US8] 更新Spec 021规格、plan、research、data-model、contract和checklist，固化空白独立任务、3+3点、2端点、可选外圆参考及权限隔离 per FR-079-FR-088/SC-031-SC-036
- [x] T093 [P] [US8] 先新增 tests/test_clean_groove_pixel_review.py，覆盖空shapes、零AUTO解析/复制、SHA/路径/身份失败、3+3与端点校验、圆弧/圆心阶段和禁用标签/权限 per FR-079-FR-087/SC-031-SC-035
- [x] T094 [P] [US8] 新增 contracts/clean-groove-pixel-review.schema.json，严格表达任务来源、PENDING/完成状态、分离真值字段及永久false权限 per FR-079/FR-080/FR-085/SC-031/SC-033
- [x] T095 [US8] 实现 tools/prepare_clean_groove_pixel_review.py 的prepare/validate子命令；所有产物Git外，prepare不解析AUTO shape，validate fail-closed per FR-079-FR-087/SC-031-SC-035
- [x] T096 [US8] 更新quickstart、README、completion-audit和evidence，给出Mac生成/校验命令及人工LabelMe步骤，明确外圆缺失时不得评姿态角精度 per FR-083/FR-085-FR-088/SC-033-SC-036
- [x] T097 运行SpecKit analyze、聚焦/全量、全部Schema、CLI、diff/JSON/媒体/绝对路径/检测阈值污染门；不读sealed part-006、不重跑140图 per SC-036
- [x] T098 提交并推送021功能分支，保持main隔离、旧污染流程DORMANT、PLC未授权，等待Mac独立验证 per SC-035-SC-036

### Phase 21 Dependencies

- T092先于T093-T094；T093红门先于T095；T095完成后执行T096-T098。
- 本阶段只使用合成临时fixture，不读取145/147原图或AUTO几何；实际Git外任务由Mac在已核验review bundle上生成。

## Phase 22: Independent Mac Gate - clean-groove pixel review preparation

- [x] T099 记录Mac对e6a8ce1的11项聚焦、408项全量、16项平台skip、41份Schema、diff/status门及145/147 Git外空白任务`shapes=0`证据；明确未重跑140 BMP、未改算法/阈值/PLC且下一步只等待145人工点标，提交推送021且不合main per SC-031-SC-036

## Phase 23: Clean-groove residual diagnostic and default-off consistency candidate

**Goal**: 用145/147正式独立墙点/端点量化AUTO残差，拆分槽口定位贡献与外圆真值缺口；增加不改变任何权威结果的默认关闭多证据候选，保护part-019已知混合边。

**Independent Test**: 临时validation/HUMAN LabelMe/runtime JSONL覆盖精确SHA关联、墙/端点/条件方向数学和所有fail-closed分支；纯数值source-consistency正负例证明候选不依赖文件/样品/固定角且永不提升姿态。

- [x] T100 [US9] 更新spec、plan、research、data-model、contract与checklist，固化墙/端点残差、条件方向、无外圆精度声明、默认关闭候选及part-019保护边界 per FR-089-FR-104/SC-037-SC-044
- [x] T101 [P] [US9] 先新增tests/test_clean_groove_residual_diagnostic.py，覆盖SHA关联、左右映射、TLS墙线、端点/中点/槽宽、无向角和±180条件方向，以及状态/SHA/物理圆/sealed/Git内失败 per FR-089-FR-096/FR-103/SC-037-SC-040
- [x] T102 [P] [US9] 新增contracts/clean-groove-residual-diagnostic.schema.json并用Draft 2020-12验证严格字段、有限值、false权限及无绝对路径/原始坐标输出 per FR-089-FR-095/SC-037-SC-040
- [x] T103 [US9] 实现tools/compare_clean_groove_pixel_truth.py，按image SHA唯一关联正式validation、HUMAN LabelMe和canonical runtime JSONL，成功产物只写Git外 per FR-089-FR-096/FR-103
- [x] T104 [P] [US9] 先新增tests/test_sidewall_source_consistency_candidate.py，覆盖contrast-only支持、part-019式端点结构拒绝、多失败/缺证据拒绝、缺失/关闭不输出及顶层结果不变 per FR-097-FR-102/SC-041-SC-043
- [x] T105 [US9] 实现algorithms/slot_pose/sidewall_consistency_candidate.py、配置Schema和默认关闭示例；只消费现有数值证据并固定全部非权威字段 per FR-097-FR-102
- [x] T106 [US9] 在legacy_adapter/contract/config Schema增加可选诊断钩子；验证开关缺失/关闭逐字段不回退，开启SUPPORTED仍保持原GROOVE_SOURCE_INCONSISTENT、valid=false、角度null和PLC空 per FR-097-FR-104/SC-042-SC-043
- [x] T107 [US9] 对服务器Git外145/147正式证据与冻结fold-03 runtime运行残差CLI，按SHA对账并生成外置报告；只汇报墙/端点及条件方向，不称最终角度精度 per SC-037-SC-040
- [x] T108 [US9] 用既有非sealed JSONL只读汇总part-008/part-019数值候选，证明已知混合负例不SUPPORTED；不重跑140 BMP、不读取part-006、不按结果调阈值 per FR-101-FR-104/SC-041-SC-044
- [x] T109 更新README、quickstart、completion-audit和evidence，记录实测残差、根因、限制、Mac命令及独立复跑门 per FR-094-FR-104/SC-040-SC-044
- [x] T110 运行SpecKit analyze、聚焦/全量、全部Schema、CLI、diff/JSON/媒体/绝对路径/阈值污染门；只提交推送021功能分支，不合main、不碰PLC per SC-043-SC-044

### Phase 23 Dependencies

- T100先于T101-T102/T104；T101与T104必须先出现红门，再实现T103/T105-T106。
- T107只读取正式145/147 Git外人工证据和现有runtime JSONL；T108只读取非sealed历史结果，不运行图像算法。
- T109-T110在实现、外置实跑与只读负例门全部通过后收尾。
