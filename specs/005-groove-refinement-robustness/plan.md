# Implementation Plan: 槽壁亚像素精修稳定性

**Branch**: `003-a2-paired-notch-stability` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-groove-refinement-robustness/spec.md`

## Summary

在现有亚像素切向梯度点与物理外圆交点之间，新增显式版本的确定性直线共识拟合。新策略枚举有足够间距的点对产生假设，按内点数、内点率、纵向覆盖、P95残差和外圆交点一致性门控，对等价假设去重后检查最佳/次佳唯一性，只对唯一内点集做TLS精修。旧v1策略可配置复现；v2不放宽2 px P95门，任一侧失败仍禁止粗角度回退。

## Technical Context

**Language/Version**: Python 3.12（项目锁定`>=3.12,<3.13`）
**Primary Dependencies**: NumPy、Pillow；亚像素采样继续委托锁定gyj函数，无新依赖
**Storage**: 配置JSON、结果JSONL、Git外JPEG/CSV/JSON审阅包
**Testing**: `unittest`、`jsonschema`契约门、合成边界样例、25张JPEG成对回放和已标注BMP开发对照
**Target Platform**: Linux服务器CPU串行，后续Mac原始BMP验收
**Project Type**: Python算法库及CLI/批处理工具
**Performance Goals**: 完整单图P95≤2.5秒，共识精修新增P95≤50 ms
**Constraints**: 峰值RSS≤1.5 GiB；最多31个侧壁点的有界确定性假设；不用随机RANSAC；不放宽残差门；不使用truth或85度参与运行时拟合
**Scale/Scope**: 25张5472×3648 JPEG开发诊断，22张v1成功、3张v1起始侧壁失败；正式truth仍不完整

## Constitution Check

*GATE: Phase 0前通过；Phase 1后复核通过。*

- **I 规格先行与场景闭环 — PASS**：17项功能需求和9项可量化结果覆盖恢复、歧义、诊断、回归和真值边界。
- **II 坐标系与姿态契约明确 — PASS**：输出仍是同一物理圆上的两个交点及环形中点，图像上方0度、顺时针正和Y轴下半轴基准不变。
- **III 质量评估与安全失败 — PASS**：数量、比例、覆盖、残差、唯一性和交点均是独立门；无粗角度回退。
- **IV 数据溯源与可复现验证 — PASS**：v1/v2成对结果、外置证据哈希和人工标注缺失项分开记录。
- **V 模块化与集成可控 — PASS**：只替换侧壁线选择，不复制外圆、槽识别或角度契约。
- **工程约束 — PASS**：性能、稳定性、资源、外置数据和安全输出均有门禁。

## Phase 0: Research Decisions

1. 不调高`max_line_residual_p95_px`：3张失败的全点P95为5.08～6.95 px，但其唯一直线主体的16个内点P95为1.33～1.49 px，问题是模型选择而不是阈值太严。
2. 不用随机RANSAC：每侧最多31点，确定性枚举最夗465对，成本可控并可复现。
3. 不只依赖内点数：同时要求内点率和直线投影覆盖，防止短局部假边获胜。
4. 在外圆交点角域对假设去重并评估次佳差距；几何不同且支持接近的假设必须失败。
5. v1完全保留，v2以配置`threshold_version`select；两者共享亚像素采样和最终几何门。

## Phase 1: Design

### Data Flow

```text
accepted real groove + physical outer circle
  -> existing subpixel tangential edge samples
  -> v1 iterative MAD-TLS OR v2 deterministic line hypotheses
  -> v2 inlier count/ratio/span/residual gates
  -> intersection-angle clustering and best/second uniqueness
  -> TLS on unique inliers
  -> existing outer-circle intersection and coarse-angle gate
  -> two-side opening midpoint
  -> existing Y-down/85-degree assessment
```

### Contracts

- v1继续输出`slot-groove-subpixel-opening/1`。
- v2输出`slot-groove-subpixel-opening/2`，新增共识策略、检测/内点/拒绝点、内点率、覆盖、假设数、最佳/次佳支持和差距。
- 配置增加共识内点率、覆盖、最小点对间距比、模型角去重和支持差距，所有值严格校验。
- 顶层`slot-pose-result/2`不升版；精修失败仍使用`GROOVE_REFINEMENT_FAILED`，细分原因在`failedChecks`。

### Verification Strategy

1. TDD先增加确定共识、圆角、离群、双线歧义、短覆盖和旧v1兼容测试。
2. 运行25张v1/v2成对回放，对旧22张统计环形角差，对新3张统计内点质量、粗细差和跨帧一致性。
3. 产生侧壁点分类叠加图和CSV，人工视觉检查新3张直线是槽壁而非纹理。
4. 复跑已标注BMP对照，但只作单样本开发证据。
5. 复跑全量、Schema、CLI、legacy、paired、004圆定位、真槽识别、批处理和污染门。

## Project Structure

```text
algorithms/slot_pose/groove_refinement.py
algorithms/slot_pose/contract.py
config/inspection.example.json
contracts/slot-pose-config.schema.json
tests/test_groove_refinement.py
tests/test_single_real_groove.py
tools/render_slot_pose_review.py
tools/summarize_slot_pose_diagnostics.py
specs/005-groove-refinement-robustness/
```

**Structure Decision**: 保持现有单仓库与单一精修模块；共识拟合作为旧精修器的版本化策略，不另建第二条姿态管线。

## Post-Design Constitution Re-check

全部门禁通过。方案不放宽原残差门，不使用业务目标选择几何，不将无truth的JPEG稳定性写成准确率，且旧策略可复现。

## Complexity Tracking

无Constitution违例或豁免。
