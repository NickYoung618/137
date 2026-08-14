# Data Model: A2双缺口槽姿态稳定检测与真实数据验收

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

## PairAssessment

| Field | Type | Rule |
|---|---|---|
| leftCandidateId, rightCandidateId | string | 指向两个不同NotchCandidate |
| separationDeg | number | 最短环形距离，`[0,180]` |
| widthRatio, prominenceRatio | number | 小值/大值，`(0,1]` |
| centerlineDeg | number | 两角在最短环形弧上的中点，`[0,360)` |
| score | number | `0..1`，距离、宽度、显著度三部分组合 |
| failedChecks | string list | 被硬门控拒绝的可解释原因 |

## PairingResult

| Field | Type | Rule |
|---|---|---|
| assessments | PairAssessment list | 全部组合，确定性排序 |
| selectedPair | PairAssessment/null | 仅当最佳得分和唯一性差距通过时非空 |
| bestScore, secondBestScore | number/null | 没有对应排名时为空 |
| scoreMargin | number/null | `best-second`；只有一个通过硬门的配对时可视为`best` |
| unique | boolean | 选中对唯一性结论 |
| failureCode | string/null | 无法配对时的稳定原因 |

## DiagnosticConfiguration

| Field | Type | Rule |
|---|---|---|
| diagnosticMode | enum | `legacy_single_notch` / `paired_notches_centerline` |
| targetSemanticsConfirmed | boolean | false时正式角始终为空 |
| profile | object | 角度/径向样本数、环带宽、平滑窗、MAD倍数和最小显著度 |
| pairing | object | 候选数、宽度/显著度、间距、比率、最佳得分和次优差距门槛 |
| maxPolarPairDisagreementDeg | positive number | paired rotation与polar rotation的最大环形差 |

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

`received → face_located → profile_extracted → candidates_extracted → mode_evaluated → diagnostic_ready`。
任一阶段可进入`failed`终态。只有`diagnostic_ready`且目标语义、机械约定、质量门和角范围全部通过，
才允许`pose_computed → succeeded`；否则仍以无角失败终止。
