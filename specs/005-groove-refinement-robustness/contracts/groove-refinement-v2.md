# Contract: Groove Refinement v2

## Configuration

`detector.groove_refinement.threshold_version` selects behavior:

- `groove-sidewall-subpixel-v1`: existing iterative MAD/TLS behavior and v1 diagnostics.
- `groove-sidewall-subpixel-v2`: deterministic consensus/TLS behavior and v2 diagnostics.

v2 additionally validates these finite fields:

```text
line_consensus_min_inlier_ratio: (0, 1]
line_consensus_min_span_ratio: (0, 1]
line_consensus_min_pair_separation_ratio: (0, 1]
line_consensus_model_merge_deg: > 0
line_consensus_min_support_margin: integer >= 1
line_consensus_max_refit_hypotheses: integer in [2, 128]
```

The consensus inlier distance gate remains the existing
`max_line_residual_p95_px`; v2 MUST NOT silently raise it.

## Diagnostic side object

```text
detectedPointCount: integer
supportPointCount: integer          # final inliers, preserved legacy meaning
rejectedPointCount: integer
lineInlierRatio: number|null
lineLongitudinalCoverage: number|null
lineFitStrategy: string
lineConsensusGatePx: number
rawLineHypothesisCount: integer
refitLineHypothesisCount: integer
lineHypothesisCount: integer
bestModelId: string|null
secondModelId: string|null
bestSupportCount: integer|null
secondSupportCount: integer|null
supportMargin: integer|null
line: {a,b,c}|null
lineResidualPx: {median,p95,max}|null
detectedPoints: [[x,y], ...]
points: [[x,y], ...]                # final inliers, backward-compatible
rejectedPoints: [[x,y], ...]
```

## Failure checks

- `<side>_insufficient_support`
- `<side>_consensus_not_found`
- `<side>_consensus_inlier_ratio`
- `<side>_consensus_span`
- `<side>_consensus_ambiguous`
- `<side>_line_residual`
- `<side>_intersection`

Any failure keeps `outerCircleIntersections`, endpoint angles and midpoint null.
Top-level behavior remains `GROOVE_REFINEMENT_FAILED`, `valid=false` and a null
formal mechanical angle.
