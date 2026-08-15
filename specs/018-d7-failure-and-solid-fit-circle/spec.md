# Feature Specification: D7失败证据与Phi实线拟合圆审核

**Feature Branch**: `main`

**Created**: 2026-08-15
**Baseline**: `c9399dadeaa4073d30f5ce134430e579f001c803`
**Status**: Implemented and verified

## Scope

在唯一人工参考运行时架构不变的前提下，查明9帧development/diagnostic中501、520的尺寸7
双边界拟合失败根因，并把Phi完整拟合圆的审核样式从虚线改为实线。检测质量门、测量数值和
有效性语义不因显示要求而改变。

## Authoritative reference

- annotation SHA-256: `018e3449c051c15f7946315bd0d7f21cd79f4d4983efca0d11c7d98f02bfffa6`
- image SHA-256: `faf357c2e6e8e58d667f76a3d9ed4f4d51ab4d451c2661cf0efbc641405b2d8b`
- 运行时只能使用这对Git外置JSON/BMP；退役资产保持零运行时角色。

## Clarifications

1. Phi完整圆是`fittedGeometry`数学模型，实线仅是审核显示样式，不代表整圈有边缘证据。
2. 绿色局部弧是本张图实际命中的`rawEdgeEvidence`，必须与完整圆同时保留。
3. 完整圆的圆心、半径和渲染坐标必须直接来自同一个`fittedGeometry`，不得另加视觉补偿。
4. 尺寸7必须显示真实拟合的A/B有限边界线段与独立公法线尺寸标注；失败时不得伪造线。
5. 501/520是否恢复只由现有图像证据和原质量门决定；证据不足时继续明确失败是合格行为。

## Functional requirements

- **FR-001**: MUST在未修改运行时代码前，从外置9帧结果与图像证据定位501/520失败侧、失败阶段、
  点数、轴对齐、拟合残差、梯度峰值、跨带一致性和平行度。
- **FR-002**: MUST分别报告primary单带、multiband恢复和v6 fallback的结果，禁止仅引用
  `tangent_boundary_fit_failed`总状态推断根因。
- **FR-003**: 预览MUST用完整实线绘制有效Phi的拟合圆，同时继续用绿色绘制实际局部弧。
- **FR-004**: LabelMe MUST输出完整`prediction:Phi12.2:fit-circle`圆和局部弧`linestrip`；整圆
  MUST保留`fittedModel=true`及`isDetectedContour=false`。
- **FR-005**: 单批报告和旧/新对照报告MUST采用相同“实线拟合圆”语义。
- **FR-006**: D7有效时MUST输出A/B边界和公法线；D7无边界证据时MUST保持显式失败/不可审核，
  不得由renderer构造替代线。
- **FR-007**: MUST不修改注册、Phi、D7质量门，不使用标称值、固定像素或目标真值补偿。
- **FR-008**: MUST不读取holdout，不提交BMP、JSONL、预览、LabelMe输出或大文件。
- **FR-009**: MUST保持权威同图D7误差不超过2 px、Phi直径误差不超过1 px。
- **FR-010**: MUST重跑9帧并报告执行、注册、D7、Phi状态和501/520逐帧证据。
- **FR-011**: MUST通过全套单测、compileall、全部JSON Schema、SpecKit prerequisites/analyze、
  `git diff --check`、退役角色残留及Git产物审计。

## Acceptance

- 成功帧与失败帧的仓库外预览均可审核；有效Phi显示蓝色实线拟合圆和绿色局部弧。
- 拟合圆坐标与结果中的`fittedGeometry.centerPx/radiusPx`逐值一致。
- 9帧不新增执行/注册/Phi/D7退化；501/520不因显示改动被伪恢复。
- 权威同图精度门、全套工程门禁全部通过。
