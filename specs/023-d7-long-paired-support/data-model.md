# Data Model: D7长范围同语义直边支持

## FrozenBoundary

- `side`: `A`或`B`
- `lineEquation`: 单位法向形式`[a,b,c]`
- `dimensionPointPx`: 原公法线交点
- `primaryPointsPx`: 原主窗口paired中点
- `primaryTransitionPairsPx`: 每个中点对应的外/内跃迁
- `primarySegmentPointsPx`: 022原有限显示段

冻结后不得改变直线方程、交点或业务值。

## SupportWindowDiagnostic

- `offsetTargetPx`: 移动窗口中心沿窄颈方向的偏移
- `side`: A/B
- `pairSupport`: 逐剖面已通过极性/峰值/宽度检查的数量
- `fitFailureStage`: 窗口整体拟合失败阶段，可为空
- `candidatePointCount`: 原始paired中点数
- `acceptedPointCount`: 同时通过冻结直线残差与连续性前置检查的数量
- `residualMedianTargetPx` / `residualMaxTargetPx`: 到冻结直线的残差
- `tangentMinimumTargetPx` / `tangentMaximumTargetPx`: 沿窄颈坐标范围

窗口整体失败不自动丢弃已通过逐剖面门的候选，但候选仍需通过冻结残差及连续性。

## ContinuousSupportSide

- `side`
- `primaryMaximumOffsetTargetPx`
- `candidateMaximumOffsetTargetPx`
- `acceptedMaximumOffsetTargetPx`
- `acceptedOffsetsTargetPx`
- `supportPointsPx`
- `supportTransitionPairsPx`
- `stopOffsetTargetPx`
- `stopReason`

状态：`primary_only` → `candidate_collected` → `continuous_accepted`；出现间隙、残差、错误极性或支持不足时进入
`stopped`，远端孤立簇保持rejected。

## D7AuditSegment

- `lineEquation`: FrozenBoundary原值
- `segmentPointsPx`: primary与连续扩展支持在冻结线上的投影极值
- `supportEvidenceMode`: `paired_transition_midpoints_only`或
  `paired_transition_midpoints_plus_contiguous_outward_paired_support`
- `supportPointsPx`: 仅扩展部分的原图中点
- `supportTransitionPairsPx`: 仅扩展部分的外/内跃迁对
- `supportClippedToNeckDirection`: 恒为true

此实体只服务审核显示，不参与D7数值或valid判定。

## State invariants

1. A/B任一侧没有连续新增时，两侧`segmentPointsPx`均保持primary值。
2. 每个support point到FrozenBoundary距离不超过现有3px门。
3. support points沿程不跨越大于两倍现有采样间距的缺口。
4. `measurementAnnotation`、D7数值、Phi及正式线方程前后完全一致。
5. v6 fallback不创建D7AuditSegment扩展，只保留legacy REVIEW对象。
