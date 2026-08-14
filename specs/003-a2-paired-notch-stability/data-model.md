# Data Model: A2多槽候选、角色几何与真实数据验收

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
| diagnosticMode | enum | `legacy_single_notch` / `paired_notches_centerline` / `multi_notch_roles` |
| targetSemanticsConfirmed | boolean | false时正式角始终为空 |
| profile | object | 角度/径向样本数、环带宽、平滑窗、MAD倍数和最小显著度 |
| pairing | object | 候选数、宽度/显著度、间距、比率、最佳得分和次优差距门槛 |
| maxPolarPairDisagreementDeg | positive number | paired rotation与polar rotation的最大环形差 |
| roleAssignment | object | 角色窗口、datum定义、分配差距、对置误差及图纸标注 |

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

`received → face_located → profile_extracted → candidates_extracted → roles_assessed → diagnostic_ready`。
任一阶段可进入`failed`终态。只有`diagnostic_ready`且目标语义、机械约定、质量门和角范围全部通过，
才允许`pose_computed → succeeded`；否则仍以无角失败终止。
