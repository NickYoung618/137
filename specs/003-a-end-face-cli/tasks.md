# Tasks: A 端面独立检测 CLI

## Phase 1: Setup

- [x] T001 更新 A 端面项目身份和依赖元数据于 `README.md`、`pyproject.toml`
- [x] T002 清除姿态引导业务目录、契约、工具、测试和规格于 `algorithms/`、`contracts/`、`tools/`、`tests/`、`specs/`

## Phase 2: Foundational

- [x] T003 记录桌面算法来源与技术决策于 `specs/003-a-end-face-cli/research.md`
- [x] T004 原样引入并锁定核心指纹于 `algorithms/end_face/core.py`
- [x] T005 [P] 定义结果数据模型于 `specs/003-a-end-face-cli/data-model.md`
- [x] T006 [P] 定义 JSON Schema 于 `contracts/a-end-face-result.schema.json`

## Phase 3: User Story 1 - 单图端面检测

- [x] T007 [US1] 增加核心来源与调用测试于 `tests/test_end_face_cli.py`
- [x] T008 [US1] 实现独立单图入口于 `algorithms/end_face/main.py`
- [x] T009 [US1] 记录外置输入使用方法于 `specs/003-a-end-face-cli/quickstart.md`

## Phase 4: User Story 2 - 严格 JSON 集成

- [x] T010 [US2] 增加契约、非有限值和失败测试于 `tests/test_end_face_contract.py`
- [x] T011 [US2] 实现版本化 JSON 契约于 `algorithms/end_face/contract.py`
- [x] T012 [US2] 实现文件/标准输出和严格退出语义于 `algorithms/end_face/main.py`

## Phase 5: User Story 3 - 来源与数据边界

- [x] T013 [US3] 更新忽略和外置数据约定于 `.gitignore`、`data/README.md`
- [x] T014 [US3] 执行核心哈希、真实参考资产和 Git 大文件审计并由 `tests/test_end_face_cli.py` 固化指纹门禁

## Phase 6: Polish

- [x] T015 运行 `tests/` 全量测试并核对 `specs/003-a-end-face-cli/` 与实现一致性

## Dependencies

- US1 依赖 T003-T006；US2 依赖 US1 的调用入口；US3 可在核心引入后独立验证。
- MVP 为 US1；US2 是对外集成必要门禁，US3 是提交前必要门禁。
