# Data Model: 单拍槽姿态初版

## SingleShotProfile

- `schemaVersion`: 初版剖面版本。
- `enabled`: 必须显式开启，禁止默认偷开。
- `diagnosticMode`: 必须为`single_real_groove`。
- `target`: 85°、±5°、左下语义和坐标契约ID。
- `sourceConsistencyPolicy`: 原始判定版本、二级裁决版本和原门不可改写声明。
- `safetyPolicy`: 单壁/遮挡/混边/歧义失败，人工真值不进运行时，PLC禁止。

## SingleShotResult

- `detectionStatus`: `DETECTED` / `DETECTION_FAILED`.
- `guidanceStatus`: `DETECTED_NEEDS_ADJUSTMENT` / `DETECTED_IN_POSITION` / `NOT_AVAILABLE`.
- `valid`: 表示单张图像的检测与几何链是否可信，不表示PLC已授权。
- `currentAngleDeg`: 相对Y轴下半轴的有符号当前角。
- `targetAngleDeg`: 85.
- `toleranceDeg`: 5.
- `correctionDeg`: 到85°的最短环形差；死区内为0。
- `rotationDirection`: `CLOCKWISE` / `COUNTERCLOCKWISE` / `NONE` / null.
- `withinTolerance`: 检测有效时的到位状态，失败时null。
- `error`: 错误码、阶段和人可读说明；成功时null。
- `plcExecution`: 初版始终null。

## StageEvidence

1. `circleLocalization`: 候选、唯一性、粗中心/半径。
2. `physicalOuterCircle`: 亚像素圆心/半径、点数、覆盖、残差和质量门。
3. `rawCandidates`: 所有暗区的角区间、显著度和亏损积分。
4. `grooveCandidates`: 几何过滤后真槽候选、评分和拒绝理由。
5. `grooveRefinement`: 两壁支持点、直线、残差、槽口端点和中点。
6. `sourceConsistency`: 原判定、原失败集、非contrast证据与二级裁决；两者并存。

## State Transitions

`RECEIVED -> CIRCLE_VALID -> ONE_GROOVE_ACCEPTED -> TWO_WALLS_REFINED -> SAME_SOURCE_ACCEPTED -> DETECTED`

任一阶段失败立即转`DETECTION_FAILED`，后续姿态和PLC字段不再计算。
