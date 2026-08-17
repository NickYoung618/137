# Data Model

## Guidance Request

- schemaVersion
- mode: `SINGLE_CAPTURE`或`HALF_TURN_PAIR`
- sampleId、requestId
- captures: 单图恰好1个，双图恰好2个且captureIndex为1/2
- imageSha256、relativePath
- halfTurn: 双图固定`nominalRotationDeg=180`、`directionRequired=false`、`executionResponsibility=EXTERNAL_HARDWARE`

## Pair Hypothesis

- first/second candidate ID和usable状态
- secondAngleInFirstPartFrameDeg = wrap360(secondAngle-180)
- angularResidualDeg = abs(wrap180(normalized-firstAngle))
- shape/profile difference与failedChecks
- eligible: passed且至少一侧usable

## Guidance Result

- detectionStatus、verificationStatus、guidanceStatus、valid
- captureMeasurements与hypotheses
- selectedMatch、measurementSource
- currentAngleDeg、targetAngleDeg=85、toleranceDeg=5
- correctionRawDeg、correctionDeg、rotationDirection、withinTolerance
- authoritative=false、posePromotionAllowed=false、plcExecution=null

## State Transitions

- disabled → EXPERIMENT_DISABLED
- invalid input → INPUT_INVALID
- no match → PAIR_EVIDENCE_INCONSISTENT
- multiple close matches → PAIR_MATCH_AMBIGUOUS
- unique match but neither usable → NO_COMPLETE_GROOVE
- unique + capture2 usable → DETECTED/CAPTURE_2_DIRECT
- unique + only capture1 usable → DETECTED/CAPTURE_1_PROPAGATED_HALF_TURN
