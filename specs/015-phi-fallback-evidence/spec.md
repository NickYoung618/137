# Feature Specification: Phi回退证据与累计圆心边界

**Feature Branch**: `main`

**Created**: 2026-08-15

**Status**: Implemented; pending Mac 2200-frame regression

## Scope

在只有一张人工真值的前提下，使用外置同一样品多帧、图像质量字段和现有参考边缘语义诊断
Phi12.2候选。修复两个已由源码与真实帧共同证明的失败保护缺口，不降低任何门限，不按文件名、
像素答案或标称尺寸特判。尺寸7本轮只保留深诊断；没有足够跨带证据的帧继续失败。

## Clarifications

- 唯一真值继续是绝对精度门；无标注多帧只提供重复性和图像证据。
- 正常帧有效率不能通过接受证据不足的legacy候选提高。
- 二次圆心搜索可以超过主窗口，但超过后若相位证据失败，不得仅凭局部窗口未触边回退。
- 相位极性失败时，legacy回退还必须证明相位点的RANSAC保留比例足够，不能只看残差和点数。

## Requirements

- **FR-001**: MUST记录`candidate_phase_inlier_fraction = phase inliers/raw phase points`。
- **FR-002**: 当失败原因仅为`phase_polarity_support_below_gate`时，legacy回退MUST同时要求
  phase inlier fraction不低于现有`min_angle_coverage_fraction`；不得新增更宽松数值。
- **FR-003**: MUST按原注册预测计算二次圆心候选的累计x/y位移及主窗口边界状态，不能把局部
  recenter窗口状态冒充全局状态。
- **FR-004**: 累计位移超过原主窗口时，只有成功的reference-phase多证据候选可以继续；相位失败
  后不得legacy fallback。
- **FR-004a**: reference-phase自身的中心边界MUST相对本次phase seed计算；相对原注册预测的累计
  位移只能作为独立global审计，不能错误套用局部recenter窗口。
- **FR-005**: MUST输出独立fallback rejection原因，保留原phase failure和所有质量字段。
- **FR-006**: MUST保持0.88→0.84两阶段半径、legacy 0.35、残差、点数、覆盖、极性、注册和
  geometry门限不变。
- **FR-007**: MUST保持唯一真值尺寸7误差<=2px、Phi直径误差<=1px。
- **FR-008**: MUST证明控制帧500/521/620不回归；521的高相位点保留率极性回退仍可通过。
- **FR-009**: 501/506/515/520与621/623必须逐帧对照；不得把单图或稀疏组声称为20帧精度。
- **FR-010**: 尺寸7的`min_consistent_bands=3`、残差、平行度和峰值门不得放宽；775/1951等
  证据不足帧继续显式失败。
- **FR-011**: 图片、LabelMe、JSONL和运行输出保持Git外置。

## Success criteria

- 合成测试拒绝“相位76/155低保留率＋极性失败”的legacy fallback。
- 合成测试允许“相位133/139高保留率＋极性失败”继续走原legacy质量门。
- 二次搜索累计越过主窗口且相位失败时拒绝；同样位移但相位成功时仍可接受。
- 真实shadow中520、623不再呈现证据不足的有效Phi；500/521/620状态保持。
- 501/1830及封存1828/1839的强phase候选允许越过原主窗口，但必须记录global boundary风险。

## Evidence boundary

唯一真值只证明一张图的像素精度。development、diagnostic和holdout没有目标真值，只能证明
状态、图像质量证据与候选行为；不能声称测量更准。静态重复性要求同一物理样品至少20张有效帧，
当前服务器清单每组最多4帧，因此结果必须为`INCOMPLETE`。
