# Implementation Plan: D7可审核直边支持

**Branch**: `main` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

## Summary

保持D7/Phi数值算法和全部质量门不变，修复D7审核证据链。主paired-transition路径只保留公法线向窄颈方向
的同语义已验收点，把有限显示段严格投影到既有直线；不以更远单梯度层撑长。预览增加D7局部放大。
v6 fallback补回其确定性重放单梯度点线，但作为独立REVIEW几何且不升级证据完整性。

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: 项目现有NumPy、Pillow；不新增OpenCV或其他依赖

**Storage**: 版本化JSON结果与LabelMe输出；所有运行产物仓库外

**Testing**: `unittest`、真实权威同图、010/030/050代表帧和5组100帧回归

**Target Platform**: Linux服务器与Mac审核环境

**Project Type**: Python算法适配层及离线审核CLI

**Performance Goals**: 100帧可完成回归；证据裁剪/显示不改变检测状态和数值

**Constraints**: 不改配置/Schema/门限/Phi；不读目标真值做运行时决策；输出仓库外

**Scale/Scope**: 1张权威真值、代表帧181/581/582/981、5组共100张

## Constitution Check

- 规格、研究、任务、测试和外置结果可追踪：PASS。
- 权威参考与目标真值边界不变：PASS。
- v6不等价证据保持REVIEW，失败安全：PASS。
- 不输出毫米或OK/NG：PASS。
- BMP、JSONL和审核图留在Git外：PASS。
- 本轮不放宽门，不用标称补偿：PASS。

## Design

### 1. Formal paired-boundary audit extent

正式测量成功后，以已有A/B直线、公法线点和通过门的paired点云为冻结证据。只保留从公法线向远离Phi圆心
的窄颈方向、且落在原残差门内的点；显示端点是这些点在直线上的最小/最大投影，不重新计算D7。
真实帧证明更远单梯度不是同一光学层，因此不得用于正式线段范围。

### 2. Legacy v6 review evidence

不修改冻结核心。适配层按v6最终`Extraction`变换调用同一个现成边界检测函数并开启diagnostics；重放两侧交点
必须与v6正式交点一致，否则不交付review证据。成功重放只写入独立review字段，正式证据数组仍为空，
`evidenceAuditStatus`仍为`unavailable`。

### 3. Rendering

- 正式A/B：橙色实线，LabelMe `prediction:7:boundary:A/B`。
- 公法线：青色，明确`measurement annotation; not an edge`。
- v6回退：紫色REVIEW线，LabelMe `review:7:legacy-boundary:A/B`；顶部保持审核警告。
- 全图预览左下增加D7局部放大和A/B标签；所有线段和LabelMe仍使用原图坐标。

### 4. Non-regression

冻结旧JSONL后运行新版本，逐帧比较状态、D7/Phi数值与重复性。证据字段允许变化，测量字段不允许变化。

## Project Structure

```text
algorithms/hole_2/current_capture.py
tools/render_hole2_batch_report.py
tools/render_hole2_batch_changes.py
tests/test_current_capture_registration.py
tests/test_current_capture_contract.py
tests/test_hole2_batch_report.py
tests/test_hole2_batch_review.py
specs/022-d7-auditable-line-support/
```

**Structure Decision**: 只改适配层证据生成和两个审核renderer；冻结`algorithms/hole_2/main.py`，不新增依赖、配置或Schema。

## Constitution Re-check

设计后无Constitution例外。冻结核心不修改；v6 review和正式paired证据分层，避免将非等价证据升级；数据仍全部外置。

## Complexity Tracking

无Constitution例外。
