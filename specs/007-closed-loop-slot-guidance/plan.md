# Implementation Plan: 单真槽闭环旋转引导

**Branch**: `003-a2-paired-notch-stability` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)

## Summary

在不改动现有外圆定位、多暗区候选、唯一真槽门和亚像素槽壁精修的前提下，新增版本化单槽闭环引导语义。可靠几何不论当前象限均为检测成功；计算到左下85°的最短图像帧修正，在80°～90°闭区强制归零。新结果契约将检测、引导和PLC权限分层，旧模式继续输出现有v2契约。

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: 现有NumPy 2.4.4、Pillow 12.2.0、锁定gyj A端面外圆/robust fit源码；无新依赖

**Storage**: Git内版本化JSON Schema、Spec Kit和脱敏摘要；Git外批结果、AUTO LabelMe和媒体

**Testing**: `unittest`、显式`jsonschema` gate、合成环绕/失败样例、25图外置回放

**Target Platform**: 当前Linux服务器离线回放，后续Mac原始BMP验收

**Project Type**: Python算法库 + 单图CLI + 批处理/审阅工具

**Performance Goals**: 当前2 CPU/7.5 GiB服务器上完整单图P95≤2.5 s、max≤4 s、串行吞吐≥0.3 image/s；新引导数学不增加图像处理通道

**Constraints**: 峰值RSS≤1.5 GiB；单帧无状态；失败不复用旧量；不写PLC/上位机；旧模式契约不回退；私有数据/路径不入Git

**Scale/Scope**: 1个新单真槽配置/结果版本，25张5472×3648 JPEG诊断回放，1张人工开发参考

## Constitution Check

### Pre-design gate

- **I 规格先行**: PASS；负责人纠正已写成用户故事、状态和数值验收。
- **II 坐标契约**: PASS；分开图像`+Y`下半轴与设备“-Y”别名，顺时针正、范围和帧变换均版本化。
- **III 质量与安全失败**: PASS；只有检测/几何失败才不可引导，PLC权限是独立安全门。
- **IV 溯源与验证**: PASS；合成、历史、唯一人工参考和25图依据边界分开报告。
- **V 模块化集成**: PASS；引导纯数学建模与执行机映射分层，不增加新模型/依赖。
- **工程门**: PASS；继承004/005延迟、吞吐和内存门，实跑记录测量方法。

### Post-design gate

契约设计使用新版本而非静默改变v2；单帧引导实体不持有前帧状态；图像量与PLC量分层。全部Constitution gate仍为PASS。

## Architecture and Data Flow

```text
existing physical outer-circle localization
  -> existing 3 raw dark candidates
  -> existing single true-groove recognition (exactly one)
  -> existing subpixel sidewalls + circle intersections
  -> existing opening midpoint radial direction
  -> NEW versioned image-frame guidance state machine
       -> valid image guidance (zero or shortest signed correction)
       -> independent PLC execution gate (blocked until mapping confirmation)
  -> NEW result v3 / review v2 / AUTO diagnostic v2
```

### Version strategy

1. `single-real-groove-pose-config/3` opt-in启用闭环引导；v1/v2分支不变。
2. `slot-single-real-groove-pose/3`包含几何和`guidance`实体，不继续对外使用误导性`PASS/FAIL`。
3. 新配置输出`slot-pose-result/3`；旧配置仍输出`slot-pose-result/2`。
4. 新review/index Schema升版，避免无版本字段漂移。

### Runtime integration

- `LegacyAEndFaceAdapter.estimate()`继续生产唯一真槽和精修证据；对v3仅在原有结果上计算纯数学引导。
- `main.run_loaded()`对v3从已验证`guidance`取图像修正，不调用需PLC映射的旧`mechanical_angle()`分支。
- `contract.build_result()`/`validate_result()`依配置版本生成/验证v2或v3；v3中`valid`代表检测和图像引导有效。
- 任何上游检测异常仍通过旧稳定错误码进入v3`DETECTION_FAILED`结果。

### Review integration

- `render_slot_pose_review.py`对v2/v3做显式分支；v3叠加图使用`DETECTED_*`状态，只有几何失败进`failures.csv`。
- 新`guidance.csv`逐图输出当前/目标/原始差/死区修正/方向/映射权限。
- `export_reference_anchored_diagnostics.py`继续输出同一AUTO几何，索引升版后增加引导字段和状态统计，人工参考仍不进运行时。

## Project Structure

### Documentation (this feature)

```text
specs/007-closed-loop-slot-guidance/
├── plan.md
├── research.md
├── data-model.md
├── contracts/guidance-output.md
├── quickstart.md
└── tasks.md
```

### Source Code (repository root)

```text
algorithms/slot_pose/
├── single_groove_pose.py
├── legacy_adapter.py
├── main.py
└── contract.py
contracts/
├── single-real-groove-pose-v3.schema.json
├── slot-pose-result-v3.schema.json
├── slot-pose-config.schema.json
└── reference-anchored-diagnostics.schema.json
tools/
├── render_slot_pose_review.py
├── summarize_slot_pose_diagnostics.py
└── export_reference_anchored_diagnostics.py
tests/
├── test_closed_loop_guidance.py
├── test_single_real_groove.py
├── test_slot_pose_contract.py
├── test_slot_pose_review.py
└── test_reference_anchored_diagnostics.py
```

**Structure Decision**: 保持现有单Python项目。纯角度/状态数学放在`single_groove_pose.py`，顶层版本契约放在`contract.py`，可视化和外置证据仍是独立tools，不把审阅或人工参考引入运行时。

## Verification Strategy

1. TDD先写三个权威示例、闭区、环绕、严格状态和PLC分层测试。
2. 用Schema验证v3成功/失败和旧v2样例；配置拒绝静默版本/目标改写。
3. 复跑legacy、paired、multi-role和single v1/v2全量测试。
4. 外置25图用v3配置重跑批检测、review和AUTO LabelMe，对照SC-006数量。
5. 记录冷启动/稳态P50/P95/max、串行墙钟吞吐、峰值RSS、机器和方法；与005基线比较。
6. 检查JSON、`git diff --check`、媒体/大文件/绝对路径污染。

## Complexity Tracking

无Constitution违例。新结果v3是避免静默改变v2消费者语义的必要版本边界，不是新算法分叉。
