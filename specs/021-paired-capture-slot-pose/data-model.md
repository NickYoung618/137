# Data Model: 双帧配对槽姿态

## PairedCaptureManifest

- schemaVersion、datasetId、coordinateConventionId
- pairs[]：sampleId、pairId、rotation、captures[2]
- captures：captureIndex、relativePath、imageSha256、captureTimestamp可选
- rotation：parameterStatus、nominalRotationDeg可空、rotationDirection可空、rotationToleranceDeg可空、conventionId

规则：captureIndex恰好{1,2}；同pair同sample；路径/SHA/pair唯一。CONFIRMED要求三个旋转值齐全；UNCONFIRMED允许空。

## PairedSlotPoseConfig

- schemaVersion、enabled（默认false）、thresholdVersion
- maxCandidatesPerFrame
- maxMatchResidualDeg、minMatchMarginDeg、minDiscriminatingRotationDeg
- maxWidth/Prominence/DeficitNormalizedDifference
- target：85°、5°、负Y起始、顺时针正

## CandidateEvidence

- captureIndex、candidateId、imageProfileAngleDeg
- halfWidthDeg、prominence、deficitArea、grooveScore
- rawCandidate、grooveAssessment、refinement、sourceConsistency
- usable、usableReasons、rejectionReasons
- profileEvidence可选

## CrossFrameHypothesis

- firstCandidateId、secondCandidateId
- secondAngleInFirstPartFrameDeg
- rotationSignedDeg、angularResidualDeg
- width/prominence/deficit normalized difference
- profileDifference可空、qualityPenalty、score
- passedChecks、failedChecks、authoritative

## PairedPoseResult

- schemaVersion、sampleId、pairId、valid
- status：EXPERIMENT_DISABLED、DIAGNOSTIC_ONLY、DETECTED、FAILED
- error：PAIR_PARAMETERS_UNCONFIRMED、PAIR_INPUT_INVALID、PAIR_CANDIDATE_LIMIT、PAIR_MATCH_NOT_FOUND、PAIR_MATCH_AMBIGUOUS、PAIR_NO_UNOBSTRUCTED_MEASUREMENT
- captures[]：图像SHA、单帧状态、完整CandidateEvidence
- hypotheses[]、selectedMatch、matchMarginDeg
- partRelativeGrooveAngleDeg：第一拍零件坐标profile角
- currentImageProfileAngleDeg：第二拍后的profile角
- currentAngleDeg：从负Y顺时针有符号
- targetAngleDeg、toleranceDeg、correctionRawDeg、correctionDeg、rotationDirection、withinTolerance
- measurementSource：CAPTURE_2_DIRECT或CAPTURE_1_PROPAGATED
- plcExecution：始终NOT_AUTHORIZED/null

## ReviewBundle

- image identity and SHA
- rawImage、simplifiedImage、contactSheet paths（索引中为输出根相对路径）
- simplifiedImage：只含019最终左右壁/端点、020 fixture候选、短标题/图例和人工确认提示
- prefilledLabelme：仅最终壁/端点/fixture的AUTO_ shapes、human_verified=false、runtime_input_allowed=false
- displaySummary：019Valid、020ErrorCode；020候选展示不改变020 valid状态
- questions：真实凹槽、fixture A/B、左右壁同源性

## ObservedAngularInterval

- candidateId、startDeg、centerDeg、endDeg、wrapsBoundary
- matchStatus、failedChecks、selectionSource（PAIR_EVIDENCE或UNASSIGNED_OBSERVATION）
- fixtureIdentityConfirmed：恒false（AUTO审阅阶段）
- boundarySemantics：angular_profile_interval
- pixelBoundaryKnown：恒false
- LabelMe shape：AUTO_observed_dark_angular_interval_* linestrip；圆周弧线只表达角区间，不是二维阴影区域

## HumanVisibleWallReview

- sourceAnnotationRelativePath、sourceAnnotationSha256、sourceShapeLabel、sourcePoints
- reviewedSemanticLabel：`human-confirmed-visible-real-groove-wall`
- humanVerified：true
- visibleWallOnly：true
- oppositeWallTruth：false
- completeOpeningTruth：false
- oppositeWallObservability：UNKNOWN或POSSIBLY_OCCLUDED
- runtimeInputAllowed：false

规则：原LabelMe及SHA不可覆盖；派生审核副本必须逐点保留原两点几何并记录来源SHA。该实体只证明一条可见真实槽壁，不提供另一壁、槽口中点或姿态真值。

## LocalSecondWallDiagnostic v3

- schemaVersion、thresholdVersion、enabled、status、authoritative=false、posePromotionAllowed=false
- coarseCandidateId、localInterval（只作证据）、anchorSides[]
- searchDomains[]：domainId、anchorSide、direction（INWARD/OUTWARD）、signedDirection、start/end/span/wrapsBoundary、seedCount、physicalLimitDeg
- hypotheses[]：canonicalPairId、wallClusterIds[2]、openingEndpointProfileDeg、metrics、checks、failedChecks、score
- experimentalCandidate：仅唯一解时存在，但仍authoritative=false
- sideSearchCandidates[]：每个domain/seed/polarity、亚像素直线候选、profile、searchStatus和failedChecks
- hypotheses[].checks[]：layer、hardGate、metric value/threshold/passed；score不得覆盖失败hardGate
- status：DISABLED、NOT_EVALUATED、LOCAL_SECOND_WALL_NOT_FOUND、MULTIPLE_LOCAL_OPENINGS、SOURCE_INCONSISTENT、UNIQUE_DIAGNOSTIC
- failureStage、errorCode：CANDIDATE_MISSING、LOCAL_SECOND_WALL_NOT_FOUND、MULTIPLE_LOCAL_OPENINGS、SOURCE_INCONSISTENT
- anchorEvidence[]：anchorSide、endpointAngleDeg、requiredOppositePolarity、line、lineSegment、support/contrast/gradient/profile
- sideSearchCandidates[]新增searchWindowDeg、rejectionStage、fitToSeedDeltaDeg、lineSegment、mergeClusterId、mergeDisposition
- sideSearchMergeClusters[]：polarity、representative、members/suppressed、domain/seed/fitted angles、fittedAngleSpreadDeg、mergeThresholdDeg、selectionRule
- canonicalWallPairs[]：无序wall cluster ID、falling/rising几何端点、原混合对复用证据、分层checks和failedChecks；同一两壁顺序反转不重复
- rawHypotheses[]与hypothesisMergeClusters[]保留为v2诊断兼容视图；v3每个canonical pair只有一个单例cluster，无顺序suppressed duplicate
- searchOutcomeSummary：每极性seed/accepted/rejection counts、cluster count/sizes和NO_EDGE_SIGNAL/SINGLE_EDGE_ATTRACTOR/MULTIPLE_EDGE_CLUSTERS
- 配置约束：inwardSearchExtentDeg/outwardSearchExtentDeg不超过maxWallSeparationDeg；maxSeedsPerDomain、maxTotalSearchJobs和maxWallCandidates为硬上限

## State Transitions

disabled → EXPERIMENT_DISABLED
enabled + invalid manifest/SHA → FAILED before matching
enabled + UNCONFIRMED rotation → DIAGNOSTIC_ONLY
enabled + confirmed + 0 match → PAIR_MATCH_NOT_FOUND
enabled + confirmed + multiple/low margin → PAIR_MATCH_AMBIGUOUS
enabled + confirmed + unique + no usable frame → PAIR_NO_UNOBSTRUCTED_MEASUREMENT
enabled + confirmed + unique + usable → DETECTED, image guidance available, PLC blocked

当前单帧只有`HumanVisibleWallReview`而无完整两壁时保持原失败状态。`PARTIALLY_OBSERVED`仅保留为未来可升版的诊断状态候选，不属于当前权威结果状态，且不得使valid或guidance可用。
