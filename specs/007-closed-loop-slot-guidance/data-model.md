# Data Model: 单真槽闭环旋转引导

## 1. SingleGroovePoseV3

- `schemaVersion`: `slot-single-real-groove-pose/3`
- `status`: `accepted | failed | ambiguous`，保留几何阶段状态。
- `geometryValid`: 外圆、唯一槽和槽口精修全部通过时为true。
- `role`: 唯一真槽candidateId与图像引导/PLC权限。
- `imageMeasurement`: 现有图像向上0°方位与径向轴。
- `datumMeasurement`: 现有图像向下0°、顺时针正的有符号当前角。
- `guidance`: 新闭环引导实体。

## 2. ImageFrameGuidance

| Field | Type | Rule |
|---|---:|---|
| `schemaVersion` | string | `slot-image-frame-guidance/1` |
| `detectionStatus` | enum | `DETECTED` / `DETECTION_FAILED` |
| `guidanceStatus` | enum | `DETECTED_NEEDS_ADJUSTMENT` / `DETECTED_IN_POSITION` / `NOT_AVAILABLE` |
| `currentAngleDeg` | number/null | detected时`[-180,180)` |
| `targetAngleDeg` | number | 固定85 |
| `toleranceDeg` | number | 固定5 |
| `acceptedRangeDeg` | pair | 固定`[80,90]`，双端包含 |
| `correctionRawDeg` | number/null | `wrapTo180(85-current)` |
| `correctionDeg` | number/null | 在位时0，否则等于raw |
| `imageFrameCorrectionDeg` | number/null | `correctionDeg`的显式图像帧别名 |
| `rotationDirection` | enum/null | `CLOCKWISE` / `COUNTERCLOCKWISE` / `NONE` |
| `withinTolerance` | boolean/null | 只有detected时为boolean |
| `coordinateConvention` | object | 圆心、x右、y下、下射线0°、顺时针正、`[-180,180)` |
| `plcExecution` | object | 独立映射安全门 |

### State invariants

```text
DETECTION_FAILED
  => guidanceStatus=NOT_AVAILABLE
  => current/raw/correction/imageFrameCorrection/direction/withinTolerance = null
  => valid=false

DETECTED + lower-left [80,90]
  => guidanceStatus=DETECTED_IN_POSITION
  => correctionDeg=imageFrameCorrectionDeg=0
  => rotationDirection=NONE, withinTolerance=true, valid=true

DETECTED + every other bearing
  => guidanceStatus=DETECTED_NEEDS_ADJUSTMENT
  => correctionDeg=wrapTo180(85-current)
  => direction follows sign, withinTolerance=false, valid=true
```

## 3. PlcExecutionGate

- `status`: `BLOCKED_MAPPING_UNCONFIRMED | READY`。
- `mechanicalCorrectionDeg`: 未确认时null；只有完整映射契约确认时可有值。
- `plcCommand`: 本轮始终null；不实现地址/缩放/字节序/握手。
- `authoritative`: 未确认时false。
- `blockers`: 至少包含`PLC_MAPPING_UNCONFIRMED`。

## 4. SlotPoseResultV3

- `schemaVersion`: `slot-pose-result/3`。
- `result.valid`: 代表当前帧检测与图像引导有效，不代表PLC可执行。
- `result.signedRelativeRotationDeg`: 与`imageFrameCorrectionDeg`相同的兼容数值位；`referenceFrame/targetFrame`必须明确它是图像帧引导。
- `result` 同时携带全部闭环字段和PLC门摘要。
- `technicalStatus`: detected时`succeeded`，detection failed时`failed`。
- `error`: detected时null；只存放检测/输入/质量稳定错误，不将PLC blocker写成顶层error。

## 5. ReviewRecordV2

- 保留圆、raw candidates、groove assessments、refinement和AUTO形状。
- 新增逐图guidance全字段。
- `failures.csv`只收录`DETECTION_FAILED`。
- `guidance.csv`收录所有图的检测/引导/方向/PLC状态。
- summary分别统计检测、引导和旋转方向。

## 6. Closed-loop transition semantics

算法不保存状态；下列是调用方状态转移：

```text
DETECTED_NEEDS_ADJUSTMENT -> execute only after future PLC gate -> recapture
recapture -> new independent detection/guidance result
DETECTED_IN_POSITION -> stop requesting rotation
DETECTION_FAILED/timeout/task mismatch -> clear prior correction and stop
```
