# Data Model: A2 跨零件圆与真槽鲁棒性

## CircleSectorEvidence

字段：schemaVersion、binCount、residualGatePx、sectors、suspectSectorIds、suspectRuns。
每个sector包含sectorId、startDeg、endDeg、wrapsBoundary、pointCount、inlierCount、
residualMedianPx、residualP95Px、residualMaxPx、suspect和reasons。无点扇区的残差为null。
连续异常扇区必须在0°边界环形合并。

## CircleRobustRefit

字段：schemaVersion、enabled、attempted、status、excludedSectorIds、retainedPointCount、
retainedAngularCoverage、initialCircle、refitCircle、centerDeltaPx、radiusDeltaPx和failedChecks。

状态为disabled、not_needed、rejected或accepted。同一圆阶段最多attempt一次。

## DarkThresholdHypothesis

字段：hypothesisId、source（mad或quantile）、sourceValue、rawThreshold、boundedThreshold、status、
rawRuns、acceptedRuns和rejectedRuns。run记录环形边界、宽度、显著度和拒绝原因。

## DeduplicatedDarkCandidate

延续NotchCandidate几何字段，新增sourceHypothesisIds、sourceThresholds和dedupClusterId。
candidateId在去重后按角中心升序分配，不包含真槽角色。

## RobustnessConfiguration

detector.dark_candidate_robustness：

- schema_version=angular-dark-candidate-robustness/1
- enabled=false
- quantile_levels严格介于0和0.5，升序唯一，最多三个
- max_hypotheses为1到4
- dedup_center_deg大于0且不超过30
- min_interval_overlap_ratio为0到1

detector.physical_outer_circle.sector_robustness：

- schema_version=physical-circle-sector-robustness/1
- enabled=false
- sector_bin_count为4到72
- min_points_per_sector为正整数
- suspect_residual_p95_multiplier不小于1
- max_excluded_sector_count小于sector_bin_count
- max_contiguous_excluded_deg介于0和180
- min_retained_angular_coverage介于0和1
- max_refit_center_delta_px和max_refit_radius_delta_px为有限正数

## RootCausePart

CSV字段：sample_id、failure_family、selection_authority、selection_provenance。sample/condition真值仍来自
009 confirmed grouping；一个sample只能出现一次。

## PartFoldPlan

- schemaVersion=a2-robustness-fold-plan/1
- planStatus为READY、INSUFFICIENT_PARTS或BLOCKED_SEALED_LEAKAGE
- priorExposure=true且strictBlind=false
- 输入文件SHA、封存sample/SHA
- families包含sample集合、策略、folds和limitations
- 每折包含完整development/validation sample集合、两侧SHA集合哈希与交集数

## RobustnessAudit

- schemaVersion=a2-robustness-audit/1
- 输入哈希、方法版本、扫描/解析行数和elapsedMs
- 每sample的顶层错误、阶段漏斗、圆残差/余量、raw/accepted槽数与拒绝原因
- accuracyEvaluated固定false
- sealedRecordsParsed固定0

## AnnotationQueueItem

字段：relativePath、sourceImageSha256、sampleId、conditionId、failureFamily、selectionRule、
selectionRank、requiredShapes和humanVerified=false。requiredShapes覆盖外圆有效弧、真槽开放边界、
槽壁、槽口端点和阴影区域，不预填算法候选。
