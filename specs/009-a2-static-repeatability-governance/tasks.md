# Tasks: A2 多组静态重复性与过渡盲测治理

**Input**: `specs/009-a2-static-repeatability-governance/` design artifacts

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: 用户明确要求聚焦、全量、Schema与真实数据dry-run；所有实现按TDD进行。

## Phase 1: Setup

- [x] T001 记录009分支、远程分歧、156项基线和外置700证据身份到 `specs/009-a2-static-repeatability-governance/evidence.md`
- [x] T002 [P] 核对 `.gitignore` 与污染门，确认inventory/grouping/结果/图片继续留在Git外
- [x] T003 [P] 新增Git安全的 `config/a2-canonical-inventory.template.csv` 与 `config/a2-confirmed-grouping.template.csv`

## Phase 2: Foundational Contracts

- [x] T004 [P] 新增 `contracts/a2-static-group-eligibility.schema.json`
- [x] T005 [P] 新增 `contracts/a2-static-repeatability.schema.json`
- [x] T006 [P] 新增 `contracts/a2-transitional-blind-lock.schema.json`
- [x] T007 在 `tools/evaluation_governance.py` 建立安全路径、CSV加载、SHA、分位数、环形统计和结果匹配共享函数

## Phase 3: User Story 1 - 可信物理分组与资格表 (P1)

**Independent Test**: 合成统一根清单验证draft拒绝、20/18/2帧、bad语义与泄漏门。

- [x] T008 [P] [US1] 在 `tests/test_a2_evaluation_governance.py` 添加统一根listed-path、空draft不可显式化、覆盖/哈希/provenance失败测试并确认失败
- [x] T009 [P] [US1] 在 `tests/test_a2_evaluation_governance.py` 添加20帧通过、18/2帧排除、bad语义阻塞和sample/source跨purpose拒绝测试并确认失败
- [x] T010 [US1] 在 `tools/evaluation_governance.py` 实现canonical inventory与confirmed grouping一一关联、统一根Manifest物化和泄漏检查
- [x] T011 [US1] 在 `tools/evaluation_governance.py` 实现逐condition静态资格判定、排除原因和class-qualified假设诊断
- [x] T012 [US1] 新增 `tools/prepare_a2_evaluation.py` CLI，输出Manifest、资格JSON/CSV与准备报告
- [x] T013 [US1] 运行US1聚焦测试并验证normal 481–498/499–500夹具零删除且均排除

## Phase 4: User Story 2 - 多组静态重复性报告 (P1)

**Independent Test**: 受控结果验证环形组内统计、跨组中心化、检测率、几何、耗时与三类引导覆盖。

- [x] T014 [P] [US2] 在 `tests/test_a2_static_repeatability.py` 添加±180环形range/std/P95和不同中心角跨组池化测试并确认失败
- [x] T015 [P] [US2] 在 `tests/test_a2_static_repeatability.py` 添加失败分母、null不补0、圆/槽点波动、耗时分位数和三引导类别测试并确认失败
- [x] T016 [US2] 在 `tools/evaluation_governance.py` 实现逐组结果提取、环形/像素/耗时统计和指导类别判定
- [x] T017 [US2] 新增 `tools/evaluate_static_repeatability.py` CLI，输出逐组CSV、版本化JSON与跨组汇总
- [x] T018 [US2] 修正 `tools/audit_slot_pose_replay.py` 的旧两帧即EVALUATED语义，使其复用严格资格或明确降为DIAGNOSTIC_ONLY
- [x] T019 [US2] 运行US2及008审计回归，确认偏离85°仍是有效检测且三类工况分开

## Phase 5: User Story 3 - 可审计过渡盲测冻结 (P2)

**Independent Test**: 选择对输入顺序稳定、只读Manifest、冻结完整sample并拒绝覆盖或泄漏。

- [x] T020 [P] [US3] 在 `tests/test_a2_evaluation_governance.py` 添加结果无关SHA排序、输入乱序、完整sample、多condition同purpose和非严格声明测试并确认失败
- [x] T021 [P] [US3] 在 `tests/test_a2_evaluation_governance.py` 添加候选为空、锁冲突、源Manifest变化和二次执行策略失败测试并确认失败
- [x] T022 [US3] 在 `tools/evaluation_governance.py` 实现固定版本选择键、blind Manifest、锁payload与稳定哈希
- [x] T023 [US3] 新增 `tools/freeze_transition_blind.py` CLI，原子地创建非严格锁且拒绝覆盖不同内容
- [x] T024 [US3] 运行US3聚焦测试并确认选择过程不接受results参数

## Phase 6: User Story 4 - Mac复现与判读 (P2)

**Independent Test**: 临时数据根端到端运行准备、冻结、报告并通过Schema。

- [x] T025 [P] [US4] 在 `tests/test_a2_evaluation_governance.py` 添加三个CLI退出码、输出路径和Schema端到端测试
- [x] T026 [US4] 更新 `README.md`、`config/README.md` 与 `specs/009-a2-static-repeatability-governance/quickstart.md` 的Mac逐条命令和判读边界
- [x] T027 [US4] 运行Mac路径形式的临时dry-run，确认输出无绝对路径污染且统一根每图一次

## Phase 7: Real-data Dry-run and Integration

- [x] T028 使用外置700 Manifest/JSONL只读派生临时confirmed grouping，运行资格/报告/冻结dry-run，不读取BMP、不重跑检测
- [x] T029 记录逐组数量、481–498/499–500排除、bad语义阻塞、三类覆盖、确定性选中sample/condition及锁SHA到 `specs/009-a2-static-repeatability-governance/evidence.md`
- [x] T030 运行全部新增Schema Draft 2020-12校验、聚焦测试和完整unittest
- [x] T031 运行 `git diff --check`、JSON解析、媒体/大文件/私有路径/人工真值污染检查

## Phase 8: Git Integration

- [x] T032 在009分支本地提交实现与规格，不改写008历史
- [x] T033 fetch并正常merge `origin/main` 到009，保留孔2/端面与槽姿态两边历史，冲突时不覆盖无关改动
- [x] T034 merge后复跑完整测试、Schema、dry-run和污染检查
- [x] T035 push 009分支；将009正常merge到本地main并push远程main，禁止force push
- [x] T036 核对远程main SHA、分支、工作树和Mac pull命令，完成最终报告
- [x] T037 [US3] 新增 `tools/run_transitional_blind_once.py` 与冻结后的development Manifest，确保未来开发排除锁定sample且盲测结果最多生成一次
- [x] T038 [US1] 新增 `tools/materialize_a2_grouping.py` 与confirmed segments契约，将少量人工确认段无结果泄漏地展开为逐图grouping
- [x] T039 [US1] 收紧正式静态资格：repeatIndex连续之外还必须captureSequence按repeat无缺帧、无倒序
- [x] T040 [US3] 在检测启动前独占写入一次性execution claim，使中途失败也不能重跑盲测

## Dependencies & Execution Order

- Phase 1→2是所有故事基础。
- US1建立Manifest/资格；US2和US3依赖US1数据模型，彼此独立。
- US4依赖前三个CLI。
- 真实dry-run只在单元/Schema通过后进行；过渡盲测仅冻结，不运行图片。
- Git集成最后执行，远程main先merge到功能分支再复测。

## Traceability

- FR-001..009 → T003,T007..T013,T025,T027
- FR-010..015 → T014..T019,T028..T030
- FR-016..019 → T020..T024,T028,T029
- FR-020..023 → T025..T036
- SC-001..011 → T008..T036

## Implementation Strategy

1. 先交付US1，消除空字段显式化与双root冲突。
2. 再交付US2，替换旧两帧审计语义并建立多组报告。
3. 再交付US3冻结承诺，始终标为非严格。
4. 最后完成Mac文档、真实dry-run与双历史安全合并。
