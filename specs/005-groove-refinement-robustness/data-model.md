# Data Model: 槽壁亚像素精修稳定性

## SidewallPointSet

| Field | Type | Rule |
|---|---|---|
| detectedPoints | point[] | 通过对比度/梯度门的全部亚像素点，顺径向采样顺序 |
| sampledPointCount | integer | 尝试的径向位置数 |
| edgeContrastMedian | number/null | 全部通过点的局部金属/槽内对比 |
| edgeGradientMedianPerPx | number/null | 亚像素梯度强度中位数 |

## SidewallConsensusHypothesis

| Field | Type | Rule |
|---|---|---|
| modelId | string | 稳定排序后的候选编号 |
| line | object | 单位法向`a,b,c` |
| inlierIndices | integer[] | 对应`detectedPoints`索引，不得丢失可追溯性 |
| inlierCount | integer | 必须达到`min_side_points` |
| inlierRatio | number | `inlierCount / detectedPointCount` |
| longitudinalCoverage | number | 内点沿线投影跨度/全点投影跨度 |
| residualPx | object | 内点median/P95/max |
| circleIntersection | point | 与物理外圆相交且靠近粗边界的点 |
| intersectionProfileDeg | number | 图像右向为0度、图像Y向下导致顺时针增加 |

## SidewallSelectionDecision

| Field | Type | Rule |
|---|---|---|
| strategyVersion | string | `deterministic-consensus-tls-v2` |
| status | enum | `accepted`, `not_found`, `ambiguous` |
| hypothesisCount | integer | 通过基本门并完成几何去重的模型数 |
| bestModelId/secondModelId | string/null | 没有时为空 |
| bestSupportCount/secondSupportCount | integer/null | 用于复算唯一性 |
| supportMargin | integer/null | `best - second`；无次佳时为空 |
| failedChecks | string[] | 稳定失败原因 |

## RefinedGrooveOpeningV2

| Field | Type | Rule |
|---|---|---|
| schemaVersion | string | `slot-groove-subpixel-opening/2` |
| thresholdVersion | string | `groove-sidewall-subpixel-v2` |
| startSide/endSide | object/null | 两侧完整点集、选择和直线诊断 |
| outerCircleIntersections | point[2]/null | 仅两侧全部通过时存在 |
| openingEndpointProfileDeg | number[2]/null | 环形顺序 |
| openingWidthDeg | number/null | `(end-start) mod 360`，必须在(0,180) |
| openingMidpointProfileDeg | number/null | 两交点的环形中点 |
| failedChecks | string[] | 任一失败时中点为空 |

## State Transition

```text
detected points
  -> no eligible model: failed/not_found
  -> multiple close-support distinct models: failed/ambiguous
  -> unique model on one side only: failed/single-side
  -> both unique models + valid intersections: accepted opening
```
