# Data Model: A2多槽候选、角色几何与真实数据验收

## AlignmentCircle / PhysicalOuterCircle

`AlignmentCircle`是历史全局配准输出的搜索先验，不表示壳体物理边界。`PhysicalOuterCircle`
记录由指纹锁定的gyj径向亚像素边缘与稳健拟圆核心生成的算法圆，并附源函数/哈希、
搜索先验、边界点数、内点数/比率、角覆盖率、P95残差、圆心偏移、半径比、阈值版本和失败项。
只有`status=accepted`时才能进入`AngularProfile`。

## PhysicalCircleTruth

`PhysicalCircleTruth`是在原始BMP上用LabelMe独立人工创建并由第二人复核的外圆真值。
它记录固定标签、标注员/复核员、truth版本、原图与LabelMe JSON的SHA-256、图像尺寸及
人工圆心/半径。`PhysicalOuterCircle`与其他算法叠加圆都不得反填或自动确认为truth。

## ManualOpenGrooveReview

`ManualOpenGrooveReview`是Git外LabelMe开发样本的离线几何审阅，不进入运行时。输入通过参数将
任意源标签映射为`outerCircleVisibleArc`和`grooveOpenBoundary`，分别要求不少于8点和6点；
点数不是语义。它记录锁定拟圆源哈希、代数初值/稳健几何圆、残差、覆盖角、槽边界连续性、
两端圆残差、径向内凹、槽口环形中点、圆周点、径向轴和象限。

`measurement`使用`slot-groove-image-angle/1`：拟合圆心为原点，x向右、y向下、图像向上0°、
顺时针正、范围`[0,360)`。`targetAssessment`使用独立`slot-groove-target/1`；物理datum定义ID或
目标角约定ID为空时，偏差、判定和机械纠偏均为空。派生LabelMe副本固定
`runtime_input_allowed=false`、`formal_truth=false`。

## AngularProfile

| Field | Type | Rule |
|---|---|---|
| sampleCount | positive integer | 与角分辨率一致，环形索引`0..n-1` |
| radialSampleCount | positive integer | 外缘环带的径向样本数 |
| shellInnerRadiusPx, shellOuterRadiusPx | finite number | `0 < inner < outer` |
| medianIntensity, madIntensity, darkThreshold | finite number | 稳健暗区阈值诊断 |
| completeRing | boolean | false时不得配对 |

## NotchCandidate

| Field | Type | Rule |
|---|---|---|
| candidateId | string | 按角排序后的稳定ID，例如`candidate-001` |
| centerDeg | number | `[0,360)`，图像x正轴为0，y向下导致顺时针增大 |
| halfWidthDeg | positive number | 连通暗区角宽的一半 |
| startDeg, endDeg | number | `[0,360)`，沿顺时针从start到end表示该区间 |
| wrapsBoundary | boolean | `startDeg > endDeg`时为true |
| prominence | positive number | 剖面中位亮度与该暗区最小亮度差 |
| deficitArea | positive number | 阈值下亮度亏损积分，用于排名 |
| rank | positive integer | 按prominence、deficitArea、centerDeg确定性排名 |

`NotchCandidate`在新管线中是`RawDarkCandidate`，仅表示达到环形暗区门槛，不表示已证明为凹槽。

## GrooveAssessment

| Field | Type | Rule |
|---|---|---|
| candidateId | string | 引用一个`RawDarkCandidate` |
| grooveScore | number | `[0,1]`可解释组合分，不替代硬门 |
| accepted | boolean | 所有必要几何门和组合分均通过时为true |
| rejectionReasons | string list | 深度、宽度、对比、边缘、连续性、外缘连通或已知遮挡冲突 |
| radialDepthPx, radialDepthRatio | number | 从壳体外缘向内连通的局部暗部深度 |
| angularWidthDeg, tangentialWidthPx | number | 环形宽度及外圆处弧长 |
| localMetalContrast | number | 候选内部与两侧金属肩部的稳健亮度差 |
| pairedEdgeSupport | number | 同时存在左/右边缘证据的径向比例 |
| contourContinuity | number | 有效边缘在径向的连续程度 |
| widthCoefficientOfVariation | number/null | 逐径向宽度变化，用于拒绝扇形/工装边界 |
| centerDriftDeg | number/null | 逐径向中心漂移，用于拒绝倾斜/遮挡边界 |
| outerConnected | boolean | 凹入证据连到标称外缘邻域 |
| thresholdVersion | string | 生成该评估的阈值集版本 |

## AcceptedGrooveCandidate

`AcceptedGrooveCandidate`是`GrooveAssessment.accepted=true`的原始候选及证据联合视图。`RoleAssignmentResult`的输入只能来自此集合。

## SingleRealGroovePose

`SingleRealGroovePose`使用显式v1或v2版本，只在显式`single_real_groove`模式下生成。
它要求`AcceptedGrooveCandidate`恰好1个；0个为`failed`，多于1个为`ambiguous`。成功时记录
`real_groove`唯一候选、物理外圆上的槽中心点、圆心到该点的径向轴、图像向上0°/顺时针正的绝对方位和象限。

v1保留原`NOT_EVALUATED`语义。v2将粗候选`startDeg/endDeg`仅作局部搜索初值，槽口测量点必须来自
两条亚像素侧壁拟合线与物理外圆交点的最短顺时针区间中点；新增`YDownDatumMeasurement`和
`TargetAssessmentV2`。`geometryValid`只表示单槽图像几何有效；是否合格由v2位置门和角度门另行决定。

## YDownDatumMeasurement

| Field | Type | Rule |
|---|---|---|
| schemaVersion | const | `slot-groove-y-down-angle/1` |
| center, grooveOpeningPoint | point | 物理外圆圆心与槽口环形中点在圆周上的点 |
| grooveOpening.startProfileDeg/endProfileDeg/midpointProfileDeg | number | `[0,360)`，追溯两侧边界与环形中点 |
| grooveOpening.midpointSource | string | 运行时v2固定`subpixel_sidewall_outer_circle_intersections` |
| offset.dx, offset.dy | number | `grooveOpeningPoint-center`，图像向右/向下分别为正 |
| position.horizontal | enum | `left` / `right` / `axis` |
| position.vertical | enum | `upper` / `lower` / `axis` |
| position.requiredRegionPassed | boolean | `left && (lower || axis)` |
| measuredFromPositiveYClockwiseDeg | number | `[-180,180)`，等价于`atan2(-dx,dy)`，从Y下半轴顺时针为正 |

## TargetAssessmentV2

`targetContract.schemaVersion=slot-groove-target/2`，固定datum定义ID、角约定ID、目标`85°`、公差`5°`、左侧和下方/水平轴位置门。

| Field | Type | Rule |
|---|---|---|
| status | enum | 几何有效时`EVALUATED`，否则`NOT_EVALUATED` |
| positionGatePassed | boolean/null | `dx<0 && dy>=0`；几何无效时为空 |
| angleTolerancePassed | boolean/null | `80<=measured<=90`；几何无效时为空 |
| toleranceStatus | enum | `PASS` / `FAIL` / `NOT_EVALUATED`；PASS需两个门同时通过 |
| signedMeasurementMinusTargetDeg | number/null | `wrap(measured-85)` |
| absoluteDeviationDeg | number/null | 有向偏差绝对值 |
| imageFrameCorrectionDeg | number/null | `wrap(85-measured)`；正顺时针、负逆时针 |
| mechanicalCorrectionDeg | number/null | B-005映射确认前为空 |
| plcCommandAuthoritative | boolean | B-005未确认时false |
| blockers | string list | 只列出未关闭的下游权限/数据门，不将FAIL伪装成检测失败 |

## RoleRule

| Field | Type | Rule |
|---|---|---|
| roleName | enum/string | 首版至少`datum_primary`、`target_left`，可选`datum_secondary` |
| expectedReferenceAzimuthDeg | number | 参考图像方位，只作显式诊断窗口 |
| maxDeviationDeg | number | `(0,180]`，候选进入该角色的环形最大偏差 |

## RoleAssignmentResult

| Field | Type | Rule |
|---|---|---|
| assessments | assignment list | 全部角色到不同候选的排列；包含每角色偏差、得分和失败项 |
| selectedRoleCandidateIds | map/null | 仅当最佳分配唯一时非空 |
| bestScore, secondBestScore | number/null | 没有对应排名时为空 |
| scoreMargin | number/null | `best-second`；未达门槛不得选角色 |
| unique | boolean | 角色分配是否唯一 |
| datumDefinition | enum | `single_candidate_ray` / `opposed_candidates_axis` |
| failedChecks | string list | 角色缺失、窗口失败、分配歧义或datum不对置 |

## DrawingAngleObservation

| Field | Type | Rule |
|---|---|---|
| datumAzimuthImageDeg, targetAzimuthImageDeg | number | `[0,360)`图像观测，不是机械命令 |
| clockwiseAngleDeg | number | datum至target的顺时针角，`[0,360)` |
| shortestSignedAngleDeg | number | `[-180,180)`环形最短有向角 |
| includedAngleDeg | number | `abs(shortestSignedAngleDeg)`，`[0,180]` |
| drawingNominalDeg, drawingToleranceDeg | number/null | 来自图纸证据的`85`/`5`，不自动获得验收语义 |
| toleranceStatus | enum | 默认`NOT_EVALUATED`；只在映射、datum及检测用途确认后可PASS/FAIL |

## LegacyPairingDiagnostic

`PairAssessment`/`PairingResult`仅作`paired_notches_centerline`兼容诊断，不是主数据模型，不表达图纸datum/target权威角色。

## DiagnosticConfiguration

| Field | Type | Rule |
|---|---|---|
| diagnosticMode | enum | `legacy_single_notch` / `paired_notches_centerline` / `multi_notch_roles` / `single_real_groove` |
| targetSemanticsConfirmed | boolean | false时正式角始终为空 |
| profile | object | 角度/径向样本数、环带宽、平滑窗、MAD倍数和最小显著度 |
| pairing | object | 候选数、宽度/显著度、间距、比率、最佳得分和次优差距门槛 |
| maxPolarPairDisagreementDeg | positive number | paired rotation与polar rotation的最大环形差 |
| grooveRecognition | object | 单帧径向/边缘/轮廓门槛、歧义带及阈值版本 |
| roleAssignment | object | 角色窗口、datum定义、分配差距、对置误差及图纸标注 |
| singleGroovePose | object | 固定恰好1个接受槽；v1为原未评定契约，v2增加Y下半轴实测、左下位置门、85±5公差和图像纠偏 |
| grooveRefinement | object | v2唯一真槽的左右亚像素侧壁、稳健直线、外圆交点、残差和精修状态 |

## ManualCircleReference

| Field | Type | Rule |
|---|---|---|
| status | enum | 单人样本为`DEVELOPMENT_REFERENCE`；独立复核和规程冻结前不得升级为验收truth |
| source.imageSha256 | SHA-256 | 精确原始图指纹；任何同图比较都必须匹配 |
| source.annotationSha256 | SHA-256 | 不可变LabelMe输入指纹 |
| fit.sourceSha256 | SHA-256 | 锁定gyj拟圆源指纹 |
| fit.pointCount | integer | 实际有限点数，不固定77/134 |
| fit.angularCoverageDeg | number | 可见弧支持角 |
| fit.circle | point + radius | robust/geometric拟合圆 |
| fit.residualPx | summary | 中位/P95/max径向残差 |
| runtimeInputAllowed | boolean | 恒为`false` |

## SubpixelGrooveOpening

| Field | Type | Rule |
|---|---|---|
| schemaVersion | string | `slot-groove-subpixel-opening/1` |
| status | enum | `accepted` / `failed`；failed时不得产生v2测量 |
| coarseCandidateId | string | 只追溯搜索初值，不作为几何真值 |
| startSide/endSide | object | 支持点数、对比、梯度、稳健线、median/P95/max线残差 |
| outerCircleIntersections | two points/null | 每侧选择邻近粗边界的唯一圆交点 |
| intersectionCircleResidualPx | two numbers/null | 数值自检；应接近浮点误差 |
| openingEndpointProfileDeg | two numbers/null | 从圆心向右为0°、图像顺时针增大 |
| openingMidpointProfileDeg | number/null | 两交点环形中点；v2业务角唯一入口 |
| failedChecks | string list | 支持不足、弱边、线残差、无/多义交点或角邻近失败 |

## AutomaticVsReferenceComparison

| Field | Type | Rule |
|---|---|---|
| schemaVersion | string | `slot-pose-reference-comparison/1` |
| status | enum | `COMPARED`；任何前置条件不满足则CLI失败，不生成伪比较 |
| imageSha256 | SHA-256 | 人工和自动记录必须一致 |
| circleDelta | object | dx、dy、distance、有符号/绝对半径差及归一化差 |
| centerErrorAngularUpperBoundDeg | number | `asin(min(1,centerDistance/referenceRadius))`的度数 |
| manualOpeningMidpointDeg | number | 人工槽边界两端的环形中点 |
| automaticOpeningMidpointDeg | number | 自动两侧壁圆交点的环形中点 |
| openingMidpointCircularDeltaDeg | number | 自动减人工的最短有向环形差 |
| productionAccuracyClaimed | boolean | 恒为`false`，直至冻结验收集和B-004阈值 |

## A2ManifestRecord

| Field | Type | Rule |
|---|---|---|
| imageId, relativePath, sha256 | string | 唯一ID、安全相对路径、原字节SHA-256 |
| datasetClass | enum | `normal` / `bad` |
| sampleId | string/null | 物理样品；正式验收不得为空 |
| conditionId | string/null | 采集条件/真值角组；不从总文件数推断 |
| repeatIndex | integer/null | 条件组内序号 |
| captureTimestamp | timestamp/null | 条件分组的可选证据 |
| captureSequence | integer/null | 单调采集序号的可选证据 |
| split | enum | `development` / `tuning` / `validation` / `acceptance` / `unassigned` |

## AngleTruthRecord

| Field | Type | Rule |
|---|---|---|
| image_sha256 | 64-char hex | 与Manifest一对一关联 |
| truth_valid | boolean | 坏图为false；正常有真值样本为true |
| truth_angle_deg | number/null | `[-180,180)`；truth_valid=false时为空 |
| truth_source, calibration_id | string/null | 生产角验收时必填 |
| sample, condition, repeat, split | scalar | 必须与Manifest一致 |

## EvaluationReport

状态为`COMPLETE`、`INCOMPLETE`或`NOT_EVALUATED`。正常报告包含环形误差MAE/P95/max、有效率、
各sample/condition的静态环形极差、跨condition的残差组均统计、错误码和耗时。坏图报告包含
false-positive数/率、错误码和耗时，不含伪造的0度。

## State Transitions

`received → alignment_circle_located → physical_outer_circle_refined → profile_extracted → raw_candidates_extracted → grooves_recognized`；
`multi_notch_roles`继续到`roles_assessed → diagnostic_ready`，`single_real_groove`在恰好1个接受槽时进入
`single_image_pose_ready`。v2继续到`groove_opening_refined → y_down_angle_measured → target_assessed`；精修失败进入
`groove_refinement_failed`且不产生测量，精修成功后无论公差PASS/FAIL都保留成功的检测与测量状态。
只有B-005下游权限全部确认后才能进入`plc_guidance_authorized`；否则以`target_assessed + plc_blocked`结束，顶层正式角仍为空。

人工审阅旁路为`external_annotation_received → open_boundary_validated → locked_circle_fit →
development_reference_ready → same_image_runtime_compared → groove_geometry_assessed → image_measurement_ready → target_assessed`；该旁路不连接
`pose_computed`，也不改变运行时状态机。
