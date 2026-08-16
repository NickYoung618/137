# Implementation Plan: A2 回放验收与根因加固

**Branch**: `008-a2-replay-integrity-hardening` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-a2-replay-integrity-hardening/spec.md`

## Summary

修复已由700条结果证明的验收完整性问题：所有最终统计和可视化以顶层 v3 result 为权威；数据集类别与姿态可用性通过独立外置语义清单显式提供；运行配置可展开为稳定、可校验、跨路径一致的有效配置；多粗槽候选只允许通过有上限的现有亚像素侧壁精修得到唯一物理槽。增加无图像重跑的 replay audit，量化阶段漏斗、状态一致性、语义阻塞和标注队列。圆/槽阈值保持不变，等待独立标注开发集。

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: NumPy 2.4.4、Pillow 12.2.0；Schema 门使用临时锁定的 `jsonschema`，生产运行时不新增依赖
**Storage**: 外置图片、JSONL、Manifest、CSV、JSON/Markdown 报告；Git 仅保存代码、Schema、规格和脱敏小证据
**Testing**: `unittest`、JSON Schema Draft 2020-12、合成几何样本、锁定700条结果的只读审计
**Target Platform**: Linux 服务器与 macOS 12+/Python 3.12 离线命令行
**Project Type**: Python 算法库与离线 CLI
**Performance Goals**: 700条 JSONL+Manifest 审计在同机 5 秒内完成且峰值内存小于512 MiB；歧义恢复最多精修3个候选，单图新增工作有硬上限
**Constraints**: 不训练；不改85°/坐标约定；不改PLC/上位机；不以700张 acceptance 调生产阈值；历史模式兼容；失败不填0；媒体和绝对现场路径不进Git
**Scale/Scope**: 700条锁定 acceptance 回放（开发期不反复跑）、小型合成/单元开发集、待补的独立标注 validation/test；单图粗槽候选上限3；v3 closed-loop 为新权威统计路径，v1/v2继续兼容

## Constitution Check

*GATE: Phase 0 前与 Phase 1 后均通过。*

| 原则 | 设计响应 | 状态 |
|---|---|---|
| I. 规格先行与场景闭环 | 008的5个用户故事、24项FR和11项SC映射到任务与测试；未确认坏图语义保留BLOCKED | PASS |
| II. 坐标系与姿态契约明确 | 不修改Spec 007图像坐标/角度契约；最终和中间状态分契约；PLC继续分离 | PASS |
| III. 质量评估与安全失败 | 质量拒绝不能被报表复活；多候选仅唯一精修幸存者可输出；0/多/超限均失败 | PASS |
| IV. 数据溯源与可复现验证 | 源配置哈希与有效配置哈希分离；Manifest语义有authority/provenance；700条只读复核 | PASS |
| V. 模块化与集成可控 | review、audit、Manifest、config、groove resolution分层；不改PLC/上位机 | PASS |
| 工程约束 | 无新生产依赖；外置数据；性能和内存有门；绝对路径污染检查 | PASS |

Phase 1 复核：所有接口均版本化或向后兼容；没有以现场路径、固定候选编号、85°目标或目录名称选择物理槽；无宪法豁免。

## Architecture and Data Flow

```text
external images + optional grouping.csv + dataset-semantics.csv
  -> make_manifest / validate_dataset
  -> manifest with explicit semantics provenance

source config
  -> load_config (merge and validate defaults)
  -> canonical effective detector/pose/assets-by-hash view
  -> effectiveConfigSha256 + optional materialized config

image -> existing circle -> raw candidates -> groove recognition
  -> 1 coarse groove: existing refinement
  -> 2..N coarse grooves and resolver enabled: bounded refine-each
       -> exactly 1 survivor: pose
       -> 0 / >1 / over-limit: fail closed

manifest + results.jsonl
  -> final-outcome consistency validator
  -> authoritative review/CSV/overlay
  -> replay audit: funnels, conditional vs authoritative label metrics,
     threshold margins, repeatability eligibility, annotation queue
```

## Root-Cause Decisions

1. **Final-result authority**: `result.*` and `error` determine actionability. `singleGroovePose.guidance` is renamed/retained as intermediate guidance and never drives final counts.
2. **Dataset semantics**: add a per-relative-path external CSV independent from grouping. `datasetClass` remains normal/bad compatibility; product, image, and pose usability are separate nullable fields.
3. **Configuration identity**: source hash remains byte hash. Effective hash canonicalizes project, pose, fully merged detector thresholds, and legacy asset hashes while excluding `config_id` and machine-specific asset paths.
4. **Schema compatibility**: source config Schema permits runtime-defaultable detector blocks; materialized effective config contains them and must satisfy the same conditional contract.
5. **Ambiguity recovery**: add an opt-in, default-disabled resolver until real labels exist. It calls the existing refiner for each accepted coarse candidate up to a hard limit; never ranks by score or target angle.
6. **Circle/recognition thresholds**: no changes in 008. Audit emits scaled threshold margins and annotation targets; production tuning is blocked.
7. **Contact sheet**: calculate column count so JPEG height stays below 65,000 px; the full image count remains represented.
8. **Evaluation-purpose isolation**: the one reviewed annotation is a development/reference case only. The already-inspected 700 replay is a locked acceptance regression, not a threshold-selection pool and not an unseen truth set. Independent validation/test accuracy remains blocked until physically isolated reviewed samples exist.

## Project Structure

### Documentation (this feature)

```text
specs/008-a2-replay-integrity-hardening/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── dataset-semantics-csv.md
│   ├── effective-config.md
│   ├── groove-ambiguity-resolution.md
│   └── replay-audit.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
algorithms/slot_pose/
├── contract.py                    # source/effective config identity
├── groove_resolution.py           # bounded refine-each uniqueness
└── legacy_adapter.py              # resolver integration

contracts/
├── slot-pose-config.schema.json
├── slot-pose-result-v3.schema.json
└── slot-pose-replay-audit.schema.json

tools/
├── make_manifest.py               # semantics CSV merge
├── validate_dataset.py            # semantics validation
├── materialize_slot_pose_config.py
├── audit_slot_pose_replay.py
├── evaluate_slot_pose.py           # authoritative pose-usability metric
└── render_slot_pose_review.py       # final-state authority/adaptive sheet

tests/
├── test_a2_replay_audit.py
├── test_data_tools.py
├── test_groove_resolution.py
├── test_single_real_groove.py
├── test_slot_pose_contract.py
├── test_slot_pose_evaluation.py
└── test_slot_pose_review.py
```

**Structure Decision**: 沿用单仓库算法库+CLI+unittest结构；新增一个纯几何解析模块和两个离线CLI，不复制圆拟合、真槽识别或槽壁精修实现。

## Test Strategy

- TDD：先写质量拒绝中间角、早期圆失败、null方向、语义清单冲突、有效配置等价哈希、多候选精修唯一性的失败测试。
- 契约：所有v3结果、有效配置和replay audit JSON通过Schema；旧输出字段保留。
- 合成：唯一/零/多个精修幸存者、候选超限、跨0°槽口、旧单候选路径。
- 外置700条：实现期不重跑图片；完成 release-candidate 后只运行一次现成 JSON/Manifest 审计，不调用图像检测；必须得到491/489/2/209和分阶段错误数。
- 数据隔离：同一 `sampleId` 或 `sourceImageSha256` 不得跨 development/validation/test/acceptance；当前独立标注 validation/test 状态必须为 `NOT_AVAILABLE`。
- 历史回归：完整unittest（含显式Schema gate）及legacy/paired/multi-role/single-groove聚焦测试。
- 污染：`git diff --check`、JSON解析、绝对Mac/证据路径、大文件和媒体后缀检查。

## Complexity Tracking

无 Constitution 违规。新增歧义模块只协调现有refiner并设置候选硬上限；未引入新模型、并发、第三方运行时依赖或第二套几何算法。
