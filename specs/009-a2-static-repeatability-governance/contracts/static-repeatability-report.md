# Static Repeatability Report Contract v1

顶层：

- `schemaVersion=a2-static-repeatability/1`
- `source`：Manifest/results SHA与记录数。
- `groupEligibility`：每组资格、帧数、排除原因。
- `groups`：每组detection、angle、geometry、timing与guidanceClass。
- `summary`：权威组计数、中心化跨组残差、最差组、三工况覆盖和bad阻塞。

失败帧留在validRate分母；失败数值字段为null。角度分布不足2个有效值时统计为null并给出`INSUFFICIENT_VALID_ANGLES`。
