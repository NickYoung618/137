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
`POSE_CONVENTION_UNCONFIRMED`、`ANGLE_OUT_OF_RANGE`、`INTERNAL_ERROR`。

多候选与paired数据仅增加在开放的`diagnostics`对象中，`schemaVersion`仍为`slot-pose-result/2`。
旧消费者可忽略`diagnosticMode`、`angularProfile`、`candidates`、`candidateSummary`和`pairing`；
任何诊断角均不是隐式PLC指令。

下游必须先检查`taskId`和`result.valid`，失败或超时立即清除上一任务角度并走现场确认的安全动作。
