# Contract: D7 audit geometry

## Formal supported boundary

For every item in `target.fittedGeometry.boundaries`:

1. `side` is `A` or `B`.
2. `segmentPointsPx` contains exactly two finite original-image points.
3. Both endpoints satisfy the same `lineEquation` within floating-point tolerance.
4. The segment lies within the projection range of the already-accepted paired-transition support; a different single-gradient layer cannot extend it.
5. The segment begins at or outward from the D7 measurement connector toward the neck.
6. No nominal dimension, target truth or filename participates.

`target.rawEdgeEvidence.boundaries` MUST retain the actual paired midpoint points and transition pairs used to justify the display extent.

## Legacy review boundary

An eligible v6 fallback MAY add:

```json
{
  "legacyReviewBoundaries": [
    {
      "side": "A",
      "semantics": "legacy_single_gradient_boundary",
      "rawPointsPx": [],
      "inlierPointsPx": [],
      "lineEquation": [0.0, 1.0, 0.0],
      "segmentPointsPx": [[0.0, 0.0], [1.0, 0.0]],
      "reviewOnly": true,
      "equivalentToFormalBoundary": false
    }
  ]
}
```

Legacy review boundaries MUST NOT be copied into formal `boundaries`, MUST NOT set `evidenceAvailable=true`, and MUST NOT change
`evidenceComplete/evidenceAuditStatus`. Missing v6 diagnostics MUST produce no review geometry.

The adapter MUST obtain this object by replaying the unchanged v6 detector with its final extraction transform. Both replayed feature
points MUST match the official v6 measurement points within numerical precision; otherwise the object MUST be omitted and the mismatch
reported. `algorithms/hole_2/main.py` remains byte-identical.

## Renderer labels

- Formal: `prediction:7:boundary:A/B`
- Measurement: `prediction:7:dimension`
- Legacy: `review:7:legacy-boundary:A/B` and `review:7:dimension`

Legacy shapes MUST carry flags `reviewOnly=true` and `equivalentToFormalBoundary=false`.

The JPEG renderer MAY include a zoomed D7 inset. The inset MUST reuse the same finite segment coordinates, MUST label A/B, and MUST NOT create additional LabelMe geometry.
