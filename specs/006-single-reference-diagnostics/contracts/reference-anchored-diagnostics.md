# Contract: Reference-Anchored Diagnostics v1

## Development reference

The profile is offline evidence, never runtime input. It MUST include source hashes, manual geometry, same-image automatic differences, `scope=DEVELOPMENT_REFERENCE_ONLY`, `runtimeInputAllowed=false` and `productionAccuracyClaimed=false`.

## Automatic LabelMe

- `imageData` MUST be null.
- `imagePath` MUST be relative to the exported annotation file.
- Top-level flags MUST include `algorithm_generated=true`, `human_verified=false`, `formal_truth=false`, `runtime_input_allowed=false`.
- All shape labels MUST begin `AUTO_` and MUST NOT equal any accepted human truth label.
- Missing measurements MUST remain null and MUST NOT be replaced by zero or the reference value.

## Index

The index is path-safe and one-to-one with the unlabeled diagnostic manifest. `observedCircularDeltaToReferenceDeg` is a circular observation only. Every batch record MUST carry `comparisonMeaning=OBSERVATION_ONLY_NOT_ACCURACY_ERROR` and `accuracyStatus=NOT_EVALUATED`. The separately hash-locked development-reference record is the only place where the same-image manual/automatic difference is reported.
