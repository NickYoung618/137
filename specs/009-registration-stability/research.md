# Research: Registration Stability Statistics

## R1 — Linear descriptive statistics

**Decision**: report count, min, max, arithmetic mean, median, linearly
interpolated fifth/ninety-fifth percentiles, and raw median absolute deviation
(MAD) for each finite linear metric.

**Rationale**: min/max expose extremes, p05/p95 reduce sensitivity to a single
frame, and MAD provides a robust spread measure. Reporting the observation
count prevents missing hypothesis fields from being mistaken for zero.

**Alternatives considered**:

- Standard deviation only: too sensitive to a wrong-instance frame and less
  interpretable on short batches.
- Scaled MAD as a normal-distribution estimator: not needed because no
  probabilistic acceptance rule is being introduced.
- Dropping incomplete metrics: hides useful partial evidence.

## R2 — Circular rotation statistics

**Decision**: calculate the mean unit vector of all finite rotation angles.
Report its signed angle, resultant length, circular standard deviation, and the
maximum/median absolute shortest angular deviations from the circular mean.

**Rationale**: ordinary mean/range fails at the signed boundary: `+179°` and
`-179°` are two degrees apart physically but 358 degrees apart numerically.
Resultant length explicitly describes directional concentration on `[0,1]`.

**Alternatives considered**:

- Unwrap in Manifest order: results depend on ordering and discontinuity seed.
- Ordinary percentiles on signed degrees: incorrect across the wrap boundary.
- Pick a fixed zero-degree reference: would make a legitimate rotated capture
  appear unstable.

## R3 — Metric extraction and normalization

**Decision**: extract center, scale and rotation from the accepted transform;
find the selected hypothesis by matching `componentIndex` to `selectedIndex`;
normalize x/y by target width/height and radius by `min(width,height)`.

**Rationale**: matching the component identifier is robust to hypothesis array
ordering. Per-frame normalization supports mixed image dimensions without
changing the recorded pixel values.

**Alternative considered**: normalize all frames against the reference image.
Rejected because target cropping or resolution changes would distort center
and radius comparisons.

## R4 — Eligibility and safe missing values

**Decision**: a record contributes only when technical execution succeeded and
registration is valid. Each metric independently filters missing, boolean, and
non-finite observations. Empty metrics serialize count zero plus null values;
one-point spreads serialize zero.

**Rationale**: registration-invalid hypotheses are diagnostic attempts, not
accepted geometry. Independent metric counts preserve partial output without
inventing values.

## R5 — Contract versioning

**Decision**: retain summary v1 and publish a separate summary v2 contract with
a required `stability` object. Per-frame diagnostic records stay on v1 because
their shape is unchanged.

**Rationale**: making a new required field under the old identifier would break
historical validation. A distinct identifier makes the JSON change explicit.

## R6 — Acceptance boundary

**Decision**: do not add stability thresholds, outlier labels, OK/NG status, or
candidate transitions. Document real Mac values only after an external run.

**Rationale**: no real-series evidence exists on the server to justify a
stability acceptance limit, and registration evidence cannot substitute for
corrected 19/30 measurement truth.
