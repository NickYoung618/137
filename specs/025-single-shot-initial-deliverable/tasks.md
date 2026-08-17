# Tasks: 单拍槽姿态初版交付

**Input**: `specs/025-single-shot-initial-deliverable/`

## Phase 1: Setup

- [x] T001 创建025独立分支并生成spec、checklist、plan、research、data-model、contract和quickstart于 specs/025-single-shot-initial-deliverable/

## Phase 2: Foundational

- [x] T002 在 tests/test_single_shot_initial_profile.py 先编写初版剖面的单拍、目标角、原门不变、默认安全、PLC阻断和非法配置TDD测试
- [x] T003 在 tools/prepare_single_shot_initial_config.py 实现Git外、版本化、可移植的单拍初版配置物化
- [x] T004 在 contracts/single-shot-initial-profile.schema.json 定义物化报告Schema，并在 tests/test_single_shot_initial_profile.py 覆盖Schema验证

## Phase 3: User Story 1 - 完整真槽输出单拍引导 (P1)

**Independent Test**: 145/147输出约29.58°当前角和约+55.42°调整量，PLC null。

- [x] T005 [US1] 用现有Git外非sealed 145/147和物化配置完成真实小样本回放，将脱敏数值与SHA记入 specs/025-single-shot-initial-deliverable/evidence.md
- [x] T006 [US1] 在 tests/test_single_shot_initial_profile.py 固化单拍成功、环形差、80/90死区和顺逆时针契约

## Phase 4: User Story 2 - 遮挡、阴影与歧义失败关闭 (P1)

**Independent Test**: 374和合成单壁/混边/多解均无角度。

- [x] T007 [US2] 在 tests/test_single_shot_initial_profile.py 固化单拍引导、不可信几何和无PLC的fail-closed契约，并沿用现有0/1/>1真槽、单壁、混边和外圆失败回归
- [x] T008 [US2] 用Git外非sealed 374运行混边回归，证明`valid=false`且引导字段全null，将脱敏证据写入 specs/025-single-shot-initial-deliverable/evidence.md

## Phase 5: User Story 3 - 小样本根因修复与可审计验收 (P2)

**Independent Test**: 未确认语义的6张图保持原失败层，工具输出最小审核问题而不调参。

- [x] T009 [US3] 在 specs/025-single-shot-initial-deliverable/evidence.md 记录141/161/441/281/261/401的修改前阶段、根因假设、可复用能力和必需人工回答
- [x] T010 [US3] 在 README.md 和 config/README.md 增加单拍初版的运行、判读、遮挡失败与双拍非前提说明

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T011 运行聚焦/全量测试、全部根Schema、CLI help、`git diff --check`及JSON/大文件/私有绝对路径污染检查
- [x] T012 运行SpecKit converge：17项FR、7项SC、13项任务与5项Constitution原则均已核对，无额外可安全完成的实现缺口；证据阻塞项保持明示
- [ ] T013 本地小步提交并推送025功能分支，不合并main、不修改PLC/HMI

## Dependencies

- T002 → T003/T004。
- T003/T004 → T005/T008。
- T005-T010 → T011 → T012 → T013。
- BLOCKED-001至BLOCKED-004不阻塒T002-T013，但阻塞对对应视觉门的任何修改。

## Implementation Strategy

先交付“145/147可输出、374及其他未可信图安全报错”的单拍初版候选；待用户对代表图给出物理语义后，每次只追加一类根因修复任务。
