# Data Model: 单人工样板无真值诊断

## DevelopmentReferenceProfile

- `schemaVersion`: `slot-pose-development-reference/1`
- `scope`: `DEVELOPMENT_REFERENCE_ONLY`
- `source`: image/annotation/circle-fit/manual-record/runtime-record SHA-256
- `manualCircle`: center, radius, residual and point coverage
- `manualMeasurements`: image-up and Y-down signed angle, quadrant
- `sameImageAutomaticDifference`: circle center/radius and circular groove-angle difference
- `targetContract`: 85°±5° and lower-left requirement, separate from measured reference pose
- `runtimeInputAllowed=false`, `productionAccuracyClaimed=false`

## AutomaticLabelMeDiagnostic

- Standard LabelMe `version`, `imagePath`, `imageHeight`, `imageWidth`, `imageData=null`
- Flags: algorithm generated; not human verified; not formal truth; runtime input forbidden
- Shapes: optional automatic physical circle, opening line, radial axis, side support lines and rejected points
- Every shape label starts with `AUTO_`

## DiagnosticIndexRecord

- `imageId`, relative image path/hash and automatic annotation relative path/hash
- Detection status/error code/stage
- Measured Y-down signed angle, quadrant and 85-degree assessment
- Development-reference angle and circular observation delta, both nullable
- Fixed `comparisonMeaning=OBSERVATION_ONLY_NOT_ACCURACY_ERROR`
- `accuracyStatus=NOT_EVALUATED`

## State Rules

```text
manifest item + exactly one result + matching image hash
  -> geometry available -> export AUTO shapes and measurements
  -> geometry unavailable -> export empty/partial shapes + explicit failure

manual review + same-image comparison hashes match
  -> development reference accepted
otherwise
  -> whole export fails before writing final index
```
