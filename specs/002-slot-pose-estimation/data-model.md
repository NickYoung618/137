# Data Model: A端面槽姿态估计

## InputImage

| Field | Type | Rule |
|---|---|---|
| path | relative/absolute path | Manifest内必须为相对路径；单图CLI可为绝对路径 |
| sha256 | 64-char hex | 按原始文件字节计算 |
| width, height | positive integer | 不得从配置猜测 |
| format, mode | string | 由解码器读取 |
| sampleId | string/null | 正式评估必填 |
| position | string/null | 表示装夹/扫角组，不从名字猜真值 |
| repeatIndex | non-negative integer/null | 组内唯一 |
| captureTimestamp | timestamp/null | 生产接入时必填 |

## LegacyAsset

| Field | Type | Rule |
|---|---|---|
| sourcePath, annotationPath, referencePath | absolute path | 只读；不得位于可写输出目录 |
| sourceSha256, annotationSha256, referenceSha256 | 64-char hex | 加载前逐项校验 |
| functionInventory | list | 记录必需函数名；缺失即失败 |

## FaceDetection

| Field | Type | Rule |
|---|---|---|
| centerX, centerY | float | 原图像素坐标 |
| radiusPx | positive float | 原图像素 |
| method | constant | `legacy_estimate_global_transform` |
| scale | positive float | 历史参考图到目标图尺度 |
| polarRotationScore | float | 历史polar估计峰显著度 |
| valid | boolean | 质量门限的结果 |

## SlotCandidate

| Field | Type | Rule |
|---|---|---|
| azimuthImageDeg | float | 图像参考坐标中的有向方位 |
| halfWidthDeg | positive float | 现有外缘notch暗区半宽 |
| prominence | positive float | 现有外缘notch亮度显著度 |
| polarRotationDeg | float | 相对历史参考图的polar旋转 |
| notchRotationDeg | float/null | 相对历史参考图的notch旋转 |
| rotationAgreementDeg | float/null | 两种旋转估计的环形差绝对值 |

## PoseConfiguration

| Field | Type | Rule |
|---|---|---|
| schemaVersion | constant | `slot-pose-config/1` |
| configId | non-empty string | 受控版本标识 |
| referenceFrame, targetFrame | string | 生产使用前不得为`PENDING` |
| mechanicalZeroImageDeg | float/null | 图像参考坐标中的零位射线 |
| positiveDirection | enum/null | `ccw`或`cw` |
| conventionsConfirmed | boolean | false时正式角度必须为空 |
| validRangeDeg | pair/null | 机械允许范围，生产前确认 |
| legacyAsset | LegacyAsset | 权威路径、SHA-256和函数清单 |
| detector | object | prominence、polar score、旋转一致性和尺度门限 |
| plcMappingConfirmed | boolean | false时禁止控制接口编码 |

## PoseResult

状态机：`received → face_detected → slot_detected → pose_computed → succeeded`；任一步可进入`failed`，
失败为终态，不得带正式角度。

| Field | Type | Rule |
|---|---|---|
| schemaVersion | constant | `slot-pose-result/2` |
| taskId | non-empty string | 一图一任务 |
| createdAtUtc | timestamp | 结果创建时间 |
| image | InputImage subset | 必含SHA-256 |
| algorithm | object | name、version、configSha256 |
| signedRelativeRotationDeg | float/null | 有效时范围`[-180,180)` |
| confidence | float/null | 有效时`[0,1]` |
| valid | boolean | 与status/error满足契约不变量 |
| technicalStatus | enum | `succeeded`或`failed` |
| error | object/null | 失败时必含code/message/stage |
| diagnostics | object | FaceDetection、槽候选摘要、候选图像方位、耗时和确认门禁 |

## GroundTruthAnnotation

| Field | Type | Rule |
|---|---|---|
| schemaVersion | constant | `slot-pose-annotation/1` |
| imagePath, imageSha256 | string | 相对路径及原图哈希 |
| sampleId, position, repeatIndex | scalar | 正式评估必填 |
| face | circle/null | centerX、centerY、radiusPx |
| slotPolygon | points/null | 目标槽区域；至少3点 |
| slotCenterline | two points/null | 有向规则仍由端面中心决定 |
| truthAngleDeg | float/null | 必须来自机械真值，不由算法标注反推 |
| truthSource | string/null | 编码器/分度盘/受控人工设置等 |
| calibrationId | string/null | 关联坐标和零位版本 |
| split | enum | `development`、`tuning`、`validation`、`acceptance` |

## EvaluationReport

绑定dataset fingerprint、算法版本、配置指纹和运行环境；包含角度MAE/P95/max、静态/动态统计、
成功率、漏检率、误检率、错误码分布和耗时mean/P50/P95/max。缺少样本、真值或阈值时状态为
`INCOMPLETE`或`NOT_EVALUATED`。
