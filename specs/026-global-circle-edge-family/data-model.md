# Data Model: 全局物理外圆边族选择

## RadialEdgeCandidate

单条射线上的一个真实观测，不允许插值或复制。

- `angleIndex` / `angleDeg`: 射线身份与图像角度。
- `x`, `y`, `radiusPx`: 亚像素观测位置。
- `gradient`, `strength`, `polarity`: 边缘证据；生产候选仅允许物理外边界极性。
- `rankKey`: 只由有限几何与强度值导出的确定性规范顺序，不含文件名、样本或候选编号。

验证：所有数值有限；每射线数量不超过配置上限；候选间径向分离满足下限。

## CircleHypothesis

由旋转等变的跨角三候选组合产生的临时圆模型。

- `centerX`, `centerY`, `radiusPx`
- `seedAngleIndices`
- `supportRayCount`, `angularCoverage`, `residualP95Px`
- `assignedCandidateKeys`: 每射线至多一个。
- `failedChecks`: 退化、搜索包络、支持、覆盖或残差失败。

状态：`seeded → assigned → preliminary-qualified | rejected | overflow`。

## CircleEdgeFamily

将参数接近且支持观测高度重叠的假设去重后得到的物理边族。

- `familyId`: 当前运行内按规范几何顺序生成，不具业务身份。
- `representativeCircle`
- `supportRayCount`, `missingRayCount`, `angularCoverage`
- `residualMedianPx`, `residualP95Px`
- `memberHypothesisCount`, `assignedCandidateKeys`
- `status`: `qualified | rejected`
- `failedChecks`

约束：同一物理族的多个种子必须合并；不同合格族不得通过评分强行合并或挑选。

## EdgeFamilyDecision

物理圆拟合前的唯一性裁决。

- `schemaVersion`: `physical-circle-edge-family-selection/1`
- `enabled`, `strategyVersion`, `status`
- `rayCount`, `candidateCount`, `missingRayCount`
- `seedCount`, `hypothesisCount`, `familyCount`, `qualifiedFamilyCount`
- `families`: 有界摘要。
- `selectedFamilyId`: 仅恰好一个合格族时非null。
- `failedChecks`: `no_qualified_edge_family`、`ambiguous_edge_families`、`family_search_overflow`等。
- `timingMs`: 候选提取、族搜索/去重、最终拟圆和总耗时。

状态：`disabled | selected | no_family | ambiguous | overflow | invalid`。

## PhysicalCircleDecision

唯一边族经过现有鲁棒拟圆和物理质量门后的权威结果。

- 复用现有`physicalCircle`、`edgePointCount`、`inlierCount`、`inlierRatio`、`angularCoverage`、`residualP95Px`、中心漂移与半径比例。
- 新增嵌套`edgeFamilySelection`，不改变既有字段语义。
- 最终状态仅`accepted | failed`；任何失败不产生槽角。

## ManualCircleEdgeFamilyAnalysis

仅Git外离线证据，运行时不可引用。

- 输入JSON/BMP/算法源码SHA和图像尺寸。
- LabelMe结构检查与人工点数。
- 人工圆、残差、弧覆盖、leave-one-out稳定性。
- 每射线所有峰到人工圆的距离、旧选择距离、missing和switch角区。
- 聚合命中率与耗时。

状态：`verified | rejected`；输入SHA、结构或有限性任一不符即拒绝。
