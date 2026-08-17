# 槽姿态输出契约 v2

权威机器可读契约为`contracts/slot-pose-result.schema.json`。输出角度是槽外向射线相对已确认机械
零位的最短带符号旋转，单位固定为度、范围固定为`[-180,180)`。

## 不变量

- `valid=true`时必须有数值角度、`0..1`置信度、`succeeded`状态且`error=null`。
- `valid=false`时正式角度和置信度均为`null`，`error`必须含稳定`code/message/stage`。
- `diagnostics.candidateAzimuthImageDeg`只供诊断；机械零位/正方向未确认时不得当作引导角。
- 结果绑定`taskId`、图像/配置SHA-256、算法版本及历史源码/标注/参考图SHA-256，不跨任务复用。
- `production_plc_mapping_confirmed=false`时不输出PLC地址、DInt编码或写控制器动作。

稳定错误码：`INPUT_INVALID`、`ASSET_MISMATCH`、`FACE_NOT_FOUND`、`SLOT_NOT_FOUND`、
`SLOT_ROTATION_INCONSISTENT`、`SLOT_FIT_FAILED`、`QUALITY_REJECTED`、
`SLOT_PAIR_NOT_FOUND`、`SLOT_PAIR_AMBIGUOUS`、`RING_TRUNCATED`、`TARGET_SEMANTICS_UNCONFIRMED`、
`PHYSICAL_OUTER_CIRCLE_FAILED`、`GROOVE_RECOGNITION_FAILED`、`GROOVE_RECOGNITION_AMBIGUOUS`、
`GROOVE_REFINEMENT_FAILED`、`GROOVE_SOURCE_INCONSISTENT`、
`FIXTURE_SHADOW_TEMPLATE_INCOMPLETE`、
`ROLE_ASSIGNMENT_FAILED`、`ROLE_ASSIGNMENT_AMBIGUOUS`、`DATUM_DEFINITION_UNCONFIRMED`、
`FEATURE_MAPPING_UNCONFIRMED`、`OUTPUT_PURPOSE_UNCONFIRMED`、
`POSE_CONVENTION_UNCONFIRMED`、`PLC_MAPPING_UNCONFIRMED`、`ANGLE_OUT_OF_RANGE`、`INTERNAL_ERROR`。

多候选与paired数据仅增加在开放的`diagnostics`对象中，`schemaVersion`仍为`slot-pose-result/2`。
旧消费者可忽略`diagnosticMode`、`angularProfile`、`candidates`、`candidateSummary`和`pairing`；
任何诊断角均不是隐式PLC指令。

`single_real_groove` v2中的`geometryValid=true`表示恰好一个真实槽通过且左右侧壁亚像素精修成功。
最终槽口中点必须来自两条稳健侧壁与gyj拟合外圆的交点，不能用粗角度格或暗区质心替代。
`datumMeasurement`给出以图像下方`+Y`为datum、顺时针正的有符号角；`targetAssessment`独立给出
左下位置门、`85°±5°`、偏差和图像纠偏。B-005未确认时返回`PLC_MAPPING_UNCONFIRMED`且顶层正式
角/置信度为空，这不等于槽识别失败或目标未评定。

下游必须先检查`taskId`和`result.valid`，失败或超时立即清除上一任务角度并走现场确认的安全动作。

## 019可选鲁棒诊断（不升顶层Schema）

`slot-pose-result/3.diagnostics`是开放扩展点，019保留顶层契约版本不变：

- `physicalOuterCircle.sectorEvidence`按圆周扇区给出点数、内点数和径向残差；空扇区残差为`null`。
- `physicalOuterCircle.robustRefit`明确记录是否启用、是否实际重拟合、排除扇区、保留覆盖、拟合漂移及拒绝原因。
- 全画面定位时，相同字段同时出现在稀疏`circleCandidates`和最终`finalPhysicalCircleDiagnostics`。
- `angularProfile.rawDarkThreshold/thresholdUsable`保留原MAD阈值；`candidateSummary.thresholdHypotheses`、
  `candidateHypothesisOrigins`和`rejectedRuns`解释分位数假设、跨假设去重和拒绝原因。

这些字段只解释检测证据，不是人工真值。增强开关关闭时，既有有效/失败判定不变；增强开启后，0个或多个
真槽、分布式圆污染、覆盖不足或重拟合漂移仍必须fail-closed并清空所有姿态角。

## 020固定阴影与槽双侧壁同源性诊断

020继续使用开放的diagnostics扩展点，不改变顶层Schema版本。fixtureShadowEvidence记录两处相机坐标固定
阴影模板的逐候选匹配、成对完整性、相似性和局部灰度/梯度剖面。固定角仅是nuisance prior，绝不是
ignore mask；原始候选必须完整保留，candidateSuppressionApplied恒为false。

grooveSourceConsistency记录槽两侧壁的灰度跃迁幅值差、梯度差、归一化局部剖面差/相关性、径向覆盖、
端点结构和每项硬门结果。任何一项不可信都以GROOVE_SOURCE_INCONSISTENT安全失败，不能把真槽一侧与
工装阴影另一侧拼成开口。槽与阴影重叠时只允许比较固定模板预测信号与额外残差；没有经人工复核的模板剖面、
没有唯一残差假设或缺少一处固定阴影时，必须输出不完整/歧义证据，不能按31度或328度直接删除候选。

两个020开关默认关闭。当前阈值和无真值回放只能作为诊断实验，不能称为生产准确率或已修复。

## 022同源性二级裁决

显式开启`detector.source_consistency_adjudication`时，槽精修诊断可新增
`sourceConsistencyAdjudication`，顶层诊断同步暴露`sidewallSourceConsistencyAdjudication`。
原`sourceConsistency`对象及其`status/metrics/checks/failedChecks`必须原样保留；新对象单独输出
`decision`（`NOT_EVALUATED`、`NOT_NEEDED`、`REJECTED`或`ACCEPTED_OVERRIDE`）、
`effectiveSourceConsistencyStatus`、逐项审计门和安全策略。仅`ACCEPTED_OVERRIDE`允许现有图像姿态链
继续，且不授权机械修正或PLC命令。配置缺失/关闭时不新增该字段，历史消费者行为不变。

该裁决不把人工LabelMe、样本编号、固定角或85°目标作为运行时输入，也不修改020的0.12原门。
缺证据、非有限值、多项原失败、遮挡、混合墙或端点结构不一致均保持fail-closed。
