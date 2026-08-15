# Contract: Full-frame Circle Localization Diagnostic v1

## Placement and compatibility

`slot-pose-result/2`顶层保持不变。新增字段位于`diagnostics.circleLocalization`。旧消费者必须允许忽略该字段。显式ROI或功能关闭时仍输出最小策略诊断，或者字段缺省；两者均不得改变顶层机械角安全规则。

## Diagnostic shape

```yaml
schemaVersion: full-frame-circle-localization/1
thresholdVersion: string
strategy: explicit_roi_legacy | otsu_components_sparse_gyj_full_gyj
status: accepted | not_found | ambiguous | overflow | refinement_failed
coordinateSystem:
  origin: image_top_left
  xAxis: right
  yAxis: down
  lengthUnit: px
searchPolicy:
  allowedCenterRegionNormalized: [xmin, ymin, xmax, ymax]
  minScale: number
  maxScale: number
  maxComponentCandidates: integer
  minScoreMargin: number
componentProposals:
  - proposalId: proposal-001
    threshold: integer
    bboxNormalized: [xmin, ymin, xmax, ymax]
    centerX: number
    centerY: number
    radiusPx: number
    referenceScale: number
    componentPixelCount: integer
    bboxAspectRatio: number
    fillRatio: number
    borderClearanceRatio: number
    status: eligible | rejected
    failedChecks: [string]
circleCandidates:
  - candidateId: circle-candidate-001
    rank: integer | null
    proposalId: proposal-001
    status: accepted | rejected
    coarsePhysicalCircle: {centerX: number, centerY: number, radiusPx: number} | null
    edgePointCount: integer
    inlierCount: integer
    inlierRatio: number
    angularCoverage: number
    residualP95Px: number | null
    centerShiftPx: number | null
    scoreComponents: {inlier: number, coverage: number, residual: number, prior: number}
    score: number | null
    failedChecks: [string]
clusters:
  - clusterId: circle-cluster-001
    memberCandidateIds: [string]
    representativeCandidateId: string
    score: number
bestCandidateId: string | null
secondCandidateId: string | null
bestScore: number | null
secondBestScore: number | null
scoreMargin: number | null
selectedCandidateId: string | null
finalPhysicalCircle: {centerX: number, centerY: number, radiusPx: number} | null
failedChecks: [string]
timingMs:
  proposalExtraction: number
  sparseAssessment: number
  selection: number
  finalRefinement: number
  totalLocalization: number
```

所有数值必须有限；不可用值用`null`，不得使用NaN、Infinity或0度占位。

## Error mapping

| Localization status | Result error code | Downstream allowed |
|---|---|---|
| `not_found` | `HOUSING_CIRCLE_NOT_FOUND` | no |
| `overflow` | `HOUSING_CIRCLE_AMBIGUOUS` | no |
| `ambiguous` | `HOUSING_CIRCLE_AMBIGUOUS` | no |
| `refinement_failed` | `PHYSICAL_OUTER_CIRCLE_FAILED` | no |
| `accepted` | downstream-defined | yes, only with final physical circle |

任何非`accepted`状态都要求：

```yaml
result.valid: false
result.signedRelativeRotationDeg: null
result.confidence: null
diagnostics.failClosed: true
```

## Config extension

`detector.full_frame_circle_locator`是可选对象，`enabled=false`保持旧行为。首版约束：

- `enabled=true`只允许`diagnostic_mode=single_real_groove`；
- 不得同时提供`face_search_roi_normalized`；
- schema、threshold method、整数上限、归一化区域、尺度/比例范围和粗物理圆配置必须严格验证；
- 未声明字段由根配置Schema拒绝，防止拼写错误静默失效。

## Truth isolation

运行时定位输入只允许图像、锁定参考几何和版本化工位配置。人工LabelMe圆、85度目标、槽候选位置、逐图truth和跨帧结果不得进入候选评分。
