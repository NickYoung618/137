# Implementation Plan: A2 多组静态重复性与过渡盲测治理

**Branch**: `009-a2-static-repeatability-governance` | **Date**: 2026-08-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/009-a2-static-repeatability-governance/spec.md`

## Summary

在不修改槽姿态检测核心的前提下，新增统一A2根清单物化、严格物理分组/静态资格校验、逐组与跨组重复性报告、以及不读取算法结果的确定性过渡盲测冻结。外置CSV/JSON与原图继续留在Git外；仓库新增版本化Schema、Mac CLI、测试与脱敏dry-run证据。

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Python标准库、既有Pillow/NumPy；JSON Schema Draft 2020-12仅测试时使用

**Storage**: 外置UTF-8 CSV、JSON Manifest、JSONL结果和JSON报告

**Testing**: `unittest`、`jsonschema`、临时目录合成清单/结果、锁定700条Manifest/JSONL只读dry-run

**Target Platform**: Linux服务器与macOS本地离线CLI

**Project Type**: Python算法库配套离线CLI

**Performance Goals**: 700条纯清单/结果报告在5秒内完成且不读取图像；Manifest哈希校验按磁盘吞吐串行执行并输出总耗时

**Constraints**: 核心算法不变；不删除/提交图像；不随机拆帧；同sample不可跨purpose；bad语义未知不进入权威静态组；过渡盲测只运行一次且非严格

**Scale/Scope**: 700张约13GB，35个20帧物理样品候选；normal末组含18帧+2帧两个condition；报告至少覆盖三类引导工况

## Constitution Check

- **I 规格先行**: 009规格、计划、任务、测试和Mac验收相互映射；核心算法变更明确出范围。
- **II 契约明确**: 统一数据根、sample/condition/repeat、purpose、角度环形统计和blind状态均版本化。
- **III 安全失败**: 空分组、短组、bad语义未知、哈希变化、泄漏或重复执行均输出明确阻塞/失败，不补0。
- **IV 数据溯源**: 原图不可变；每图SHA、分组authority/provenance、配置/Manifest/lock哈希进入外置报告。
- **V 模块化**: 数据治理、冻结、报告与运行时算法解耦；复用既有batch与结果契约。
- **工程门**: 单元/契约/Schema/真实数据dry-run/性能/污染检查均进入任务。

Phase 0结论：无宪法豁免。Phase 1复核：接口均为离线版本化文件契约，核心运行时未耦合人工分组或盲测真值。

## Architecture and Data Flow

```text
external canonical inventory.csv (one declared A2 root)
  + external confirmed-segments.csv
  -> materialize_a2_grouping.py
       exact no-overlap coverage, no algorithm results
       -> external confirmed-grouping.csv
  + external confirmed-grouping.csv
  + optional external dataset-semantics.csv
  -> prepare_a2_evaluation.py
       validate path/hash/coverage/provenance/leakage
       -> canonical grouped manifest.json
       -> static-group-eligibility.json/csv

grouped manifest (results absent)
  -> freeze_transition_blind.py
       deterministic sample-only SHA ranking
       -> transitional-blind-manifest.json
       -> transitional-blind-lock.json + SHA-256

grouped manifest + batch results.jsonl
  -> evaluate_static_repeatability.py
       per-condition circular/geometry/timing metrics
       -> static-repeatability.json/csv
       -> group-eligibility.csv

release-candidate only:
  transitional blind manifest -> existing run_slot_pose_batch.py once
  -> blind result, evaluated separately and marked NON_STRICT_TRANSITIONAL
```

## Design Decisions

1. **One root, listed paths only**: 新物化器以inventory为全集，不递归发现class；`relative_path`相对显式`--data-root`，从而兼容根下normal图与`坏/`子目录。
2. **Draft is not grouping**: inventory可空sample/condition/repeat；confirmed grouping必须全覆盖且三字段完整，二者采用不同loader/Schema。
3. **Group eligibility is acquisition eligibility**: 20帧、same sample/condition、连续repeat、语义门决定是否进入权威组；检测失败仍留在分母。
4. **Circular within-group statistics**: 以组圆均值中心化，报告range、sample std和P95绝对残差；跨组只池化组内残差并报告最差组。
5. **Geometry extraction stays diagnostic**: 仅从最终结果的现有diagnostics读取physical circle和groove opening；缺失为null+reason，不回退算法。
6. **Blind selection is result-independent**: 对每个候选sample的排序键使用固定版本盐与其排序后源图SHA集合；输入顺序不影响选择。冻结完整sample，不按condition拆分。
7. **Existing 700 is non-strict**: 锁文件固定写`NON_STRICT_TRANSITIONAL`与`priorExposure=true`；正式test保持BLOCKED。
8. **Class-qualified fallback**: 未证实normal/bad跨目录物理映射时，外部grouping必须使用例如`normal:part-001`与`bad:part-001`，报告记录假设。

## Project Structure

### Documentation (this feature)

```text
specs/009-a2-static-repeatability-governance/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── canonical-inventory.md
│   ├── confirmed-grouping.md
│   ├── static-repeatability-report.md
│   └── transitional-blind-lock.md
├── checklists/requirements.md
├── evidence.md
└── tasks.md
```

### Source Code (repository root)

```text
tools/
├── evaluation_governance.py
├── materialize_a2_grouping.py
├── prepare_a2_evaluation.py
├── evaluate_static_repeatability.py
├── freeze_transition_blind.py
└── run_transitional_blind_once.py
contracts/
├── a2-static-group-eligibility.schema.json
├── a2-static-repeatability.schema.json
├── a2-transitional-blind-lock.schema.json
└── a2-transitional-blind-execution.schema.json
config/
├── a2-canonical-inventory.template.csv
├── a2-confirmed-segments.template.csv
└── a2-confirmed-grouping.template.csv
tests/
├── test_a2_evaluation_governance.py
└── test_a2_static_repeatability.py
README.md
config/README.md
```

**Structure Decision**: 沿用单仓库Python CLI结构，将共享纯函数集中于`evaluation_governance.py`；
分段展开、物化、冻结、一次执行和统计CLI只组合既有批处理，不复制核心检测实现。

## Test Strategy

- TDD聚焦：空draft、统一根、重复路径/哈希、20/18/2帧、bad语义、sample/lineage跨purpose、固定选择、输入乱序、二次冻结。
- 环形数学：±180跨界、三种引导状态、失败null、不同组中心角、P95与sample std解析值。
- 几何/耗时：圆心、半径、槽口点波动和P50/P95/max；字段缺失不补0。
- Schema：4个新增JSON Schema Draft 2020-12自检并验证CLI夹具。
- 回归：完整既有156项测试，确保核心算法零差异。
- 真实dry-run：只读现有700 Manifest/JSONL，派生仓库外临时权威分组，验证normal 481–498与499–500排除、bad语义阻塞、确定性选组与报告；不重跑700张BMP。
- Mac smoke：quickstart用临时外置路径完成inventory→grouping→manifest→report→freeze命令。

## Integration and Git Strategy

1. 在009分支完成SpecKit与实现提交。
2. fetch后将`origin/main`正常merge进009，保留孔2/端面与槽姿态两条历史，不重写。
3. 解决冲突时仅合并共享文档/配置，不删除任一侧功能；完整复测。
4. push 009分支；本地main正常merge 009；push main。禁止force push。

## Complexity Tracking

无宪法违例；不新增外部运行时依赖或并发。
