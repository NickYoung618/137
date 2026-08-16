# Tasks: D7 v6回退首版有效性诊断

## Phase 1: Specify

- [x] T001 核验基线HEAD、工作树和Mac冻结反馈，记录到`specs/021-d7-v6-release-validity/research.md`
- [x] T002 完成`specs/021-d7-v6-release-validity/spec.md`和`checklists/requirements.md`

## Phase 2: Plan

- [x] T003 追溯v6两侧边界质量条件和fallback准入条件，记录到`research.md`
- [x] T004 统计010/030来源、审核状态、质量分布和静态重复性，记录到`research.md`
- [x] T005 完成`plan.md`、`data-model.md`、`contracts/initial-release-decision.md`和`quickstart.md`

## Phase 3: Diagnostic decision

- [x] T006 [US1] 区分计算时边缘证据与交付时可审核证据，写入`analysis.md`
- [x] T007 [US2] 比较全部无效、无条件有效和条件保留三种方案，写入`analysis.md`
- [x] T008 [US2] 给出技术检测、审核、精度和生产处置矩阵，写入`contracts/initial-release-decision.md`
- [x] T009 [US3] 确认本增量没有算法、门限、Phi、配置、Schema或测试改动

## Phase 4: Validation and analyze

- [x] T010 运行有效性/证据独立契约测试和v6 fallback失败保护测试
- [x] T011 运行SpecKit prerequisites并完成只读artifact consistency analyze
- [x] T012 运行`git diff --check`及大文件/运行产物/修改范围审计
- [x] T013 更新`analysis.md`和本任务清单，明确首版条件保留结论

## Dependencies

- T003--T005依赖T001--T002。
- T006--T009依赖T003--T005。
- T010--T013依赖T006--T009。

## MVP

T001--T013：形成不改运行时的首版发布决策，并保留失败保护和独立证据状态。
