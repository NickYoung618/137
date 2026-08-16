# Data Model: D7参考剖面相位

## ReferenceProfileModel

- `side`: A或B
- `axis`: 参考测量轴单位向量
- `tangent`: 参考边界切向单位向量
- `offsetsRefPx`: 剖面坐标
- `intensityTemplate`: 归一化灰度模板
- `gradientTemplate`: 归一化梯度模板
- `contrast`: 参考局部对比度
- `polarityOrder`: 两个参考过渡的符号顺序
- `source`: 权威参考角色和指纹

## ProfilePhaseCandidate

- `side`
- `valid`
- `failureReason`
- `matchedPointsTargetPx`
- `fittedLineTarget`
- `segmentPointsTargetPx`
- `supportCount`
- `scoreMedian`
- `scoreMarginMedian`
- `shiftMedianTargetPx`
- `shiftMadTargetPx`
- `fitResidualTargetPx`
- `axisCosine`

## D7ReferenceProfileAudit

- `candidateValid`
- `failureReason`
- `measurementTargetPx`
- `boundaryA` / `boundaryB`
- `parallelismDeg`
- `formalMeasurementUpdated`: 必须为false

## TruthSideComparison

- `truthSourcePath` / `truthSha256`
- `side`
- `manualLine`
- `candidateLineDistancePx`
- `outerTransitionDistancePx`
- `midTransitionDistancePx`
- `innerTransitionDistancePx`
- `nearestEvidenceLayer`
- `measurementLengthErrorPx`

TruthSideComparison只能由离线工具产生，不得进入检测入口。
