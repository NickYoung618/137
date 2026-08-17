# Data Model: D7可审核直边支持

## FormalBoundaryEvidence

| Field | Meaning |
|---|---|
| `side` | `A`或`B` |
| `pointsPx` | 同语义paired-transition中点，目标图原坐标 |
| `transitionPairsPx` | 每个中点对应的外/内两次原始梯度位置 |
| `lineEquation` | 归一化直线`a*x+b*y+c=0` |
| `segmentPointsPx` | 支持投影范围内的两个共线显示端点 |
| `supportDirection` | 从公法线指向窄颈直段的方向 |
| `supportClippedToNeckDirection` | 固定表示圆柱侧点未进入显示范围 |

状态：只有A/B均有raw points和finite segment时，正式证据才为`complete`。

## LegacyReviewBoundary

| Field | Meaning |
|---|---|
| `side` | `A`或`B` |
| `semantics` | `legacy_single_gradient_boundary` |
| `rawPointsPx` | 以v6最终变换和同一检测函数重放的单梯度边缘点 |
| `inlierPointsPx` | 重放的v6稳健直线拟合内点 |
| `lineEquation` | 重放且与v6正式交点一致的拟合线 |
| `segmentPointsPx` | 重放内点投影范围，不作外推 |
| `replayMatchesMeasurement` | 只有重放交点与v6正式交点一致时为true并允许输出 |
| `reviewOnly` | 固定为true |
| `equivalentToFormalBoundary` | 固定为false |

该对象不参与`_d7_evidence_audit()`，不能改变measurement/evidence状态。

## Preview audit inset

预览可从原图裁出D7局部区域并放大显示正式或REVIEW A/B、公法线及A/B标签。该对象只存在于JPEG显示层，
不产生新坐标、不进入JSON契约，也不改变LabelMe原图坐标。

## MeasurementAnnotation

公法线两端来自冻结的正式测量点，`valuePx`等于当前D7。它不属于raw edge或detected contour。

## State transitions

```text
paired formal success -> formal A/B complete -> evidenceComplete=true
v6 fallback success -> legacy review A/B present -> evidenceComplete=false / unavailable
v6 evidence incomplete -> no review A/B -> evidenceComplete=false / unavailable
measurement invalid -> no formal/review geometry -> not_applicable
```
