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

## State Transitions

disabled → EXPERIMENT_DISABLED
enabled + invalid manifest/SHA → FAILED before matching
enabled + UNCONFIRMED rotation → DIAGNOSTIC_ONLY
enabled + confirmed + 0 match → PAIR_MATCH_NOT_FOUND
enabled + confirmed + multiple/low margin → PAIR_MATCH_AMBIGUOUS
enabled + confirmed + unique + no usable frame → PAIR_NO_UNOBSTRUCTED_MEASUREMENT
enabled + confirmed + unique + usable → DETECTED, image guidance available, PLC blocked
