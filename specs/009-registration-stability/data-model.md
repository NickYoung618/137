# Data Model: Registration Stability Statistics

## LinearDistribution

- `count`: number of finite eligible observations
- `minimum`, `maximum`: observed extrema
- `mean`, `median`: common location summaries
- `p05`, `p95`: deterministic linearly interpolated percentiles
- `medianAbsoluteDeviation`: median absolute distance from the median

When `count=0`, every descriptive value is null. When `count=1`, extrema,
mean, median and percentiles equal the observation and MAD is zero.

## CircularDistribution

- `count`: number of finite eligible angles
- `circularMeanDeg`: signed mean direction in `[-180,180)`
- `resultantLength`: unit-vector mean magnitude in `[0,1]`
- `circularStdDeg`: wrap-safe circular standard deviation
- `maximumAbsoluteDeviationDeg`: largest shortest angular distance from mean
- `medianAbsoluteDeviationDeg`: median shortest angular distance from mean

When `count=0`, all descriptive values are null. When the mean direction is
undefined because resultant length is effectively zero, direction/deviation
values are null while count and resultant length remain available.

## RegistrationStability

- `eligibleRecordCount`: technically succeeded and registration-valid records
- Linear distributions:
  - `targetCenterXPx`, `targetCenterYPx`
  - `targetCenterXRatio`, `targetCenterYRatio`
  - `targetRadiusPx`, `targetRadiusRatio`
  - `scale`, `rotationScore`, `rotationMargin`
  - `instanceSelectionMargin`, `edgeCoverageRatio`, `circularResidualRatio`
- Circular distribution: `rotationDeg`

## RegistrationBatchSummaryV2

Retains the v1 entities:

- dataset/Manifest provenance
- algorithm/core/config provenance
- reference-image provenance
- image/technical/registration counts
- failure reason distribution
- diagnostic JSONL fingerprint

Adds required `stability: RegistrationStability`.

## Extraction invariants

- Eligibility never depends on short-line truth or any legacy measurement.
- `selectedIndex` is matched to hypothesis `componentIndex`; list position is
  not assumed.
- Missing per-frame image dimensions prevent only the corresponding normalized
  values from contributing.
- Statistics never change per-frame records, registration validity, candidate
  validity, measurements, localization, or completeness.
