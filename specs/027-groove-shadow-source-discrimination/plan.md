# Implementation Plan: 真实槽与固定装置阴影源判别

**Branch**: `027-groove-shadow-source-discrimination` | **Date**: 2026-08-18 | **Spec**: [spec.md](./spec.md)

**Input**: Mac在`d776c4d2f25b985fb4e50d4978cc3868cc59c6f7`上的700张A2回放、207张失败索引与新增人工语义要求。

## Summary

先把已观察700张转换为不可调参的逐图失败账本，再增加一个严格默认关闭、只依赖单图像素与几何证据的来源裁决层。裁决层不新增可调判别阈值，而是汇总既有粗识别、物理双壁精修、外圆肩部端点和原始sidewall source-consistency结果：只有唯一候选通过全部既有门、所有竞争候选有明确物理失败证据且所有全局质量门仍通过时，既有姿态链才可继续；混合、遮挡、多个存活候选、缺失证据、低`polar_score`或上游失败一律fail-closed。

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: NumPy 2.4.4、Pillow 12.2.0；标准库`csv`/`json`/`hashlib`
**Storage**: 运行时JSON诊断；Git外JSON/CSV/PNG验收产物
**Testing**: `unittest`、Draft 2020-12 JSON Schema校验、冻结真实回放
**Target Platform**: Linux服务器与Apple Silicon/Intel Mac离线单图运行
**Project Type**: Python离线视觉算法库及诊断CLI
**Performance Goals**: 复用同一适配器的热态单图墙钟P95不高于2.5秒
**Constraints**: 单拍；有界候选；所有旧门限保持不变；关闭时行为兼容；不访问sealed part-006；不修改PLC/HMI
**Scale/Scope**: 已观察700张、207张失败账本；新物理分离验收集大小由数据持有者冻结后确定

## Constitution Check

### Phase 0 gate

- **Safety over availability — PASS**: 任一不确定、混合、遮挡、歧义、质量或上游失败均保持空姿态/空PLC。
- **Versioned contracts — PASS**: 新配置、运行时诊断和离线报告均使用独立Schema版本；旧结果根Schema不做破坏性修改。
- **Reproducible evidence — PASS**: 报告绑定HEAD、配置SHA、图像SHA、证据Schema与数据用途；700张明确为observed diagnostic。
- **No target leakage — PASS**: 运行时不读取文件名、sampleId、角度白名单、人工标签、历史帧或reviewed-700规则。
- **Bounded runtime — PASS**: 最多复用现有3个ambiguity候选的精修；不新增图像解码、全图扫描或无界假设。
- **PLC boundary — PASS**: 不修改PLC/HMI；任何失败结果继续由既有结果构建器清空控制字段。
- **Independent validation — CONDITIONAL PASS**: 设计保留独立manifest门；当前尚无新物理零件，故只能完成开发，不能完成最终验收或生产声明。

### Phase 1 re-check

数据模型将“运行时图像证据”与“离线人工语义”隔离，裁决函数的输入类型不含路径、人工类别或目标角；契约将`not_evaluated`作为显式状态，防止用缺失证据推断通过。没有宪法例外。

## Project Structure

### Documentation (this feature)

```text
specs/027-groove-shadow-source-discrimination/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── groove-shadow-source-diagnostic.schema.json
│   └── groove-shadow-source-report.schema.json
└── tasks.md
```

### Source Code (repository root)

```text
algorithms/slot_pose/
├── contract.py
├── groove_shadow_discrimination.py
├── groove_resolution.py
└── legacy_adapter.py

contracts/
├── slot-pose-config.schema.json
├── groove-shadow-source-diagnostic.schema.json
└── groove-shadow-source-report.schema.json

config/
├── inspection.example.json
└── README.md

tools/
├── trace_groove_shadow_sources.py
└── render_slot_pose_review.py

tests/
├── test_groove_shadow_discrimination.py
├── test_groove_resolution.py
├── test_slot_pose_contract.py
├── test_single_real_groove.py
└── test_trace_groove_shadow_sources.py
```

**Structure Decision**: 沿用现有单项目布局。纯裁决状态机独立于适配器；适配器只编排现有候选证据并附加有界诊断；离线追踪工具不参与运行时决策；完整证据与叠加图只写Git外目录。

## Delivery Phases

1. **Observed evidence ledger**: 对包、700张JSONL、207张失败索引做SHA联结与阶段映射；人工A/B未逐图给出时保留`not_labeled`。
2. **Pure disposition model**: 实现无新增数值阈值的三态裁决与候选来源摘要，覆盖排序/ID/旋转不变性和非有限输入。
3. **Runtime integration**: 默认关闭；开启时复用现有ambiguity refinement和原source-consistency，不覆盖原错误优先级或全局质量门。
4. **Contracts and tooling**: 严格配置Schema、开放根诊断内的嵌套版本Schema、离线报告/CSV/可用原图时的代表性叠加图。
5. **Verification**: 单元、聚焦、全仓、根Schema、026回归、热态性能和工作树检查。
6. **Independent acceptance**: 等待新物理零件manifest与人工类别冻结后一次性执行；未到达时明确标记blocked，不宣称准确率提升且不启用生产默认。

## Complexity Tracking

无宪法违规，无需例外。
