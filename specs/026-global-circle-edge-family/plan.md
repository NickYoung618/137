# Implementation Plan: 全局物理外圆边族选择

**Branch**: `026-global-circle-edge-family` | **Date**: 2026-08-18 | **Spec**: [spec.md](spec.md)

## Summary

在现有物理外圆阶段增加默认关闭、版本化的全局边族选择：每条射线只采样一次并保留有界 bright-to-dark 候选，使用确定性、旋转等变的圆假设将跨角度观测归为物理圆族，要求唯一预选赢家后才调用仓库现有鲁棒拟圆，并原样执行现有物理圆质量门。0个、多族、搜索溢出、缺失或最终质量不合格均fail-closed。161人工长弧仅用于Git外离线评估；运行时不读取人工证据。

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: 标准库、NumPy、Pillow，仓库内`algorithms.end_face.core`

**Storage**: 版本化JSON/JSONL诊断；BMP、人工LabelMe和大结果留Git外

**Testing**: `unittest`、Draft 2020-12 JSON Schema、合成圆族测试、Git外小样本回放与同机成对性能基准

**Target Platform**: Linux服务器与macOS离线验证

**Project Type**: 离线CLI+可嵌入算法库

**Performance Goals**: 同机单图总P95不高于2.5秒；在025约225ms余量内完成候选与族裁决

**Constraints**: 单拍、每射线单次采样、有界候选/假设、确定性、原质量门不变、无固定角mask、运行时不读人工真值、不读sealed part-006、PLC/HMI不变、不得合并main

**Scale/Scope**: 开发141/161/441；145同零件正对照；held-out 281/401两个不同物理零件；不用700张循环调参

## Constitution Check

*GATE: Phase 0前与Phase 1后均必须通过。*

- **I. 规格先行与场景闭环 — PASS**：026的用户故事、FR、SC、开发/验证分组和失败语义可双向追踪。
- **II. 坐标系与姿态契约明确 — PASS**：不改变`image-y-down-clockwise-signed/1`、85°±5°、死区或最短有符号角；圆失败仍无姿态。
- **III. 质量评估与安全失败 — PASS**：0/多族、overflow、缺失与原圆门失败均显式失败；不补点、不复用旧角。
- **IV. 数据溯源与可复现验证 — PASS**：JSON/BMP/manifest与算法记录SHA；开发、正对照、held-out按物理零件隔离；人工数据仅Git外评估。
- **V. 模块化与集成可控 — PASS**：边缘原语、边族裁决、既有鲁棒拟圆、质量门和结果适配保持分层；功能默认关闭且配置/诊断版本化。

Phase 1设计复核：上述五项仍为PASS；接口契约明确候选、族、唯一赢家和失败状态，quickstart覆盖Schema、CLI、性能、污染与跨零件门。无Constitution豁免。

## Project Structure

### Documentation (this feature)

```text
specs/026-global-circle-edge-family/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── circle-edge-family-selection.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
algorithms/end_face/core.py                    # 锁定上游核心，逐字节不修改
algorithms/slot_pose/circle_edge_candidates.py # 槽姿态共享的生产/诊断有界多峰原语
algorithms/slot_pose/physical_outer_circle.py  # 全局边族预选、唯一性、现有拟圆/质量门
algorithms/slot_pose/full_frame_circle_locator.py
algorithms/slot_pose/legacy_adapter.py
algorithms/slot_pose/contract.py
contracts/slot-pose-config.schema.json
contracts/physical-circle-edge-family-diagnostic.schema.json
contracts/manual-circle-edge-family-analysis.schema.json
config/inspection.example.json
tools/trace_circle_edge_families.py
tools/analyze_manual_circle_edge_families.py
tools/prepare_single_shot_initial_config.py
tests/test_physical_outer_circle.py
tests/test_full_frame_circle_locator.py
tests/test_legacy_adapter.py
tests/test_slot_pose_contract.py
tests/test_circle_edge_family_trace.py
tests/test_manual_circle_edge_family_analysis.py
tests/test_single_shot_initial_profile.py
```

**Structure Decision**: 不建立第二套拟圆器。生产多峰提取放在仓库现有A端面核心，物理圆模块只负责有界全局族裁决；唯一赢家进入同一个`robust_fit_circle`与同一套`_fit_quality`。离线人工真值投影独立放在tools，禁止被运行时导入。

## Delivery Phases

1. 固化161人工圆与旧选择根因报告，输出Git外且带SHA/稳定性/逐射线投影。
2. TDD定义生产多峰原语、旋转等变族裁决、同族去重、0/多族/overflow失败。
3. 接入物理圆 sparse/final 与直接路径，保持功能默认关闭、旧调用兼容和原质量门不变。
4. 物化显式v3单拍候选配置；冻结开发、正对照和held-out清单，先开发后解封验证。
5. 运行聚焦、全量、根Schema、CLI、静态重复性、同机性能、Git污染和私有路径门。
6. 仅在161/145真值、141/161/441开发证据及281/401跨零件验证同时成立时提交并推送独立分支；不合并main。

## Complexity Tracking

无Constitution违反项。新增圆族层是已确认“逐射线选错不同边族”的最小根因修复；训练模型、固定角mask、门限放宽和第二套拟圆均被拒绝。
