# Result v2 Diagnostic Extension

`schemaVersion` remains `slot-pose-result/2`. Existing top-level, `result`, `technicalStatus`, and `error`
fields are unchanged. Consumers may ignore all fields below.

```text
diagnostics.diagnosticMode: legacy_single_notch | paired_notches_centerline | multi_notch_roles | single_real_groove
diagnostics.targetSemanticsConfirmed: boolean
diagnostics.face.searchRoiNormalized: [x_min, y_min, x_max, y_max] | null
diagnostics.physicalOuterCircle: {
  status, thresholdVersion, sourceAlgorithm, sourceSha256,
  alignmentCircle, searchPriorCircle, physicalCircle,
  edgePointCount, inlierCount, inlierRatio, angularCoverage,
  residualP95Px, centerShiftPx, radiusRatioToSearchPrior,
  radiusRatioToAlignment, failedChecks
}
diagnostics.angularProfile: {
  sampleCount, radialSampleCount, shellInnerRadiusPx, shellOuterRadiusPx,
  medianIntensity, madIntensity, darkThreshold, completeRing
}
diagnostics.candidates: [{
  candidateId, centerDeg, halfWidthDeg, startDeg, endDeg,
  wrapsBoundary, prominence, deficitArea, rank
}]
diagnostics.rawCandidates: [{
  candidateId, centerDeg, halfWidthDeg, startDeg, endDeg,
  wrapsBoundary, prominence, deficitArea, rank
}]
diagnostics.grooveRecognition: {
  thresholdVersion, minimumRequiredCount, acceptedCount, status,
  assessments: [{
    candidateId, grooveScore, accepted, rejectionReasons,
    radialDepthPx, radialDepthRatio, angularWidthDeg, tangentialWidthPx,
    localMetalContrast, leftEdgeContrast, rightEdgeContrast,
    pairedEdgeSupport, contourContinuity, widthCoefficientOfVariation,
    centerDriftDeg, outerConnected, thresholdVersion
  }]
}
diagnostics.grooveCandidates: [{
  candidateId, centerDeg, halfWidthDeg, startDeg, endDeg,
  wrapsBoundary, prominence, deficitArea, rank,
  grooveScore, radialDepthPx, tangentialWidthPx,
  pairedEdgeSupport, contourContinuity, thresholdVersion
}]
diagnostics.singleGroovePose: {
  schemaVersion: slot-single-real-groove-pose/1,
  status: accepted | failed | ambiguous,
  expectedAcceptedGrooveCount: 1,
  acceptedGrooveCount, geometryValid,
  role: {
    schemaVersion: single-real-groove-role/1,
    name: real_groove, status, candidateId,
    mechanicalGuidanceAuthoritative: false
  },
  imageMeasurement: null | {
    schemaVersion: slot-groove-image-angle/1,
    coordinateConvention, azimuthDeg,
    profileAzimuthXRightClockwiseDeg, quadrant,
    circlePoint, radialAxis
  },
  targetAssessment: {
    schemaVersion: slot-groove-target-assessment/1,
    targetContract, status: NOT_EVALUATED,
    signedMeasurementMinusTargetDeg: null,
    mechanicalCorrectionDeg: null, blockers
  }
}
diagnostics.candidateSummary: {count, bestCandidateId, secondCandidateId, prominenceGap}
diagnostics.pairing: {
  selectedCandidateIds, centerlineDeg, separationDeg, widthRatio,
  prominenceRatio, bestScore, secondBestScore, scoreMargin, unique,
  pairedRotationDeg, polarPairAgreementDeg, failedChecks
}
diagnostics.roleAssignment: {
  assessments, selectedRoleCandidateIds, selectedRoleAzimuthsDeg,
  bestScore, secondBestScore, scoreMargin, unique, datumDefinition,
  failedChecks,
  drawingAngle: {
    datumAzimuthImageDeg, targetAzimuthImageDeg, clockwiseAngleDeg,
    shortestSignedAngleDeg, includedAngleDeg, datumOppositionErrorDeg,
    drawingNominalDeg, drawingToleranceDeg, toleranceStatus
  }
}
diagnostics.drawingEvidence: {
  kind: drawing_geometry_intent_only,
  label: "85°±5° (Z106)",
  provesA2FeatureMapping: false
}
```

For every invalid result, `result.signedRelativeRotationDeg` and `result.confidence` remain `null`.
Diagnostic angles are image-frame observations and are never implicit machine commands.
`drawingAngle.toleranceStatus`与`result.signedRelativeRotationDeg`分属尺寸判定和机械纠偏契约，不得互相代替。

`diagnostics.candidates`作为旧诊断别名仍保留原始暗区；新消费者必须区分`rawCandidates`与
`grooveCandidates`。`multi_notch_roles`的角色分配只允许引用`grooveCandidates`。

`single_real_groove`显式要求恰好一个`grooveCandidates`元素，不运行`roleAssignment`。该条件通过时
`singleGroovePose.geometryValid=true`且图像绝对方位可用；物理datum未确认时，顶层result仍
`valid=false`、正式角为空，错误码为`DATUM_DEFINITION_UNCONFIRMED`。这不是槽识别失败。

`diagnostics.face.radiusPx`是历史配准半径，不是物理外圆。`multi_notch_roles`必须先获得
`physicalOuterCircle.status=accepted`，才能用`physicalCircle`提取原始候选和评估凹入。
`sourceAlgorithm`/`sourceSha256`标识实际复用的gyj源函数和锁定源文件；该算法圆是
诊断输出，不得被当作LabelMe人工外圆truth。
