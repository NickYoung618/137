# Result v2 Diagnostic Extension

`schemaVersion` remains `slot-pose-result/2`. Existing top-level, `result`, `technicalStatus`, and `error`
fields are unchanged. Consumers may ignore all fields below.

```text
diagnostics.diagnosticMode: legacy_single_notch | paired_notches_centerline
diagnostics.targetSemanticsConfirmed: boolean
diagnostics.angularProfile: {
  sampleCount, radialSampleCount, shellInnerRadiusPx, shellOuterRadiusPx,
  medianIntensity, madIntensity, darkThreshold, completeRing
}
diagnostics.candidates: [{
  candidateId, centerDeg, halfWidthDeg, startDeg, endDeg,
  wrapsBoundary, prominence, deficitArea, rank
}]
diagnostics.candidateSummary: {count, bestCandidateId, secondCandidateId, prominenceGap}
diagnostics.pairing: {
  selectedCandidateIds, centerlineDeg, separationDeg, widthRatio,
  prominenceRatio, bestScore, secondBestScore, scoreMargin, unique,
  pairedRotationDeg, polarPairAgreementDeg, failedChecks
}
```

For every invalid result, `result.signedRelativeRotationDeg` and `result.confidence` remain `null`.
Diagnostic angles are image-frame observations and are never implicit machine commands.
