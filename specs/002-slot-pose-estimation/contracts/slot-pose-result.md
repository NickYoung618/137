# Slot Pose Result Contract v2

运行时权威JSON Schema由仓库根目录`contracts/slot-pose-result.schema.json`提供。

## Invariants

- `schemaVersion`固定为`slot-pose-result/2`，角度单位固定为`deg`。
- `valid=true`要求：`signedRelativeRotationDeg`与`confidence`为数值、status为`succeeded`、error为空、
  坐标约定已确认、质量通过且角度处于有效范围。
- `valid=false`要求：正式角度与置信度为空、status为`failed`、error含稳定code/message/stage。
- `diagnostics.candidateAzimuthImageDeg`可在机械约定未确认时用于离线诊断，但不得被PLC适配层当作
  正式相对角。
- 结果必须绑定taskId、图像SHA-256、算法版本、配置SHA-256、历史源/标注/参考图SHA-256和UTC创建时间。
- 结果不可跨taskId复用，失败后不得回填上一张有效角度。

## Angle Semantics

`signedRelativeRotationDeg`为槽外向射线相对机械零位射线的最短有向旋转，范围`[-180,180)`。
方向由配置的`positiveDirection`定义；未确认时结果无效。

## Stable Error Codes

`INPUT_INVALID`、`FACE_NOT_FOUND`、`SLOT_NOT_FOUND`、`SLOT_ROTATION_INCONSISTENT`、`SLOT_FIT_FAILED`、
`QUALITY_REJECTED`、`POSE_CONVENTION_UNCONFIRMED`、`ANGLE_OUT_OF_RANGE`、`INTERNAL_ERROR`。
