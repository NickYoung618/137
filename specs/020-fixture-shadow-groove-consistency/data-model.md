# Data Model: 固定阴影与真槽同源性

## FixtureShadowTemplate

- schemaVersion、templateId、coordinateFrameId、enabled
- centerDeg、maxCenterDriftDeg
- halfWidthDeg、maxHalfWidthDeltaDeg
- prominenceReference、deficitAreaReference及各自允许归一化差
- intensityProfile、gradientProfile：固定长度人工参考数组，可为空；为空时禁止残差分解
- profileSampleCount、templateSource、humanVerified

## FixtureCandidateMatch

- candidateId、templateId
- centerDistanceDeg、widthNormalizedDifference
- prominenceNormalizedDifference、deficitNormalizedDifference
- rawIntensityProfile、normalizedIntensityProfile、normalizedGradientProfile
- intensityProfileMae、gradientProfileMae、profileCorrelation
- passedChecks、failedChecks、matchScore、status

角度命中不会改变候选集合；match只是诊断证据。

## FixturePairEvidence

- status：complete、incomplete、ambiguous、disabled
- templateMatches、selectedCandidateIds
- pairProminenceRatio、pairDeficitRatio、pairProfileSimilarity
- failedChecks

两模板必须各有唯一匹配且成对证据通过才是complete。

## OverlapHypothesis

- hypothesisId、sourceCandidateId、templateId
- modelKind：fixture_only或fixture_plus_groove_residual
- observedDeficitProfile、predictedFixtureProfile、residualProfile
- residualStartDeg、residualEndDeg、residualArea、modelResidual
- status、failedChecks

假设不会覆盖原始候选。0、多解或参考剖面缺失时不产生姿态。

## SidewallProfileEvidence

- sideId、polarity、radialPositionsNormalized
- edgeContrastProfile、edgeGradientProfile
- rawCanonicalGrayProfile、normalizedCanonicalGrayProfile
- metalLevelProfile、grooveLevelProfile
- supportCount、radialCoverage

## SidewallSourceConsistency

- schemaVersion、thresholdVersion、enabled、status
- contrastNormalizedDifference、gradientNormalizedDifference
- normalizedProfileMae、normalizedProfileCorrelation
- radialCoverageDifference、endpointStructureDifference
- 每项threshold、margin、passed和failedChecks

## State Transitions

disabled → legacy refinement unchanged
enabled + invalid config → configuration rejected before image read
enabled + refinement failed → upstream refinement failure
enabled + consistency rejected → GROOVE_SOURCE_INCONSISTENT
enabled + multiple survivors → GROOVE_RECOGNITION_AMBIGUOUS
enabled + one survivor → existing single groove pose and guidance
