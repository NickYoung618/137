# Contract: Wall Source Family v2

## Configuration

The v2 object is strict, explicitly enabled and paired:

```json
{
  "schema_version": "groove-wall-edge-family/2",
  "enabled": true,
  "strategy_version": "shared-longitudinal-wall-family-v2",
  "max_peaks_per_row": 4,
  "min_peak_separation_px": 1.5,
  "max_hypotheses": 64,
  "min_shared_support_count": 16,
  "min_shared_span_ratio": 0.7,
  "max_direction_delta_deg": 0.5,
  "max_shared_separation_p95_px": 6.0,
  "max_shared_separation_px": 6.0,
  "max_endpoint_chord_distance_px": 6.0,
  "max_endpoint_angle_delta_deg": 0.25,
  "max_radial_alignment_delta_deg": 8.0
}
```

All numeric values are finite and positive; ratios are in `(0,1]`; counts and hypothesis limits are bounded. Schema/strategy mixing is rejected before image execution. These v2 values do not alter any existing recognition, line residual, support-margin, source, fixture, circle or polar threshold.

## Runtime Decision

The side diagnostic reports:

- `wallFamilySchemaVersion`, `wallFamilyStrategyVersion`;
- `rawHypothesisCount`, `physicalSourceFamilyCount`, `eligiblePhysicalSourceFamilyCount`;
- stable hypothesis summaries and family membership;
- bounded pair comparisons with shared support/span, direction, signed/absolute separation, endpoint deltas, thresholds, margins and failed checks;
- one observed representative plus radial-alignment delta/pass per family;
- best/second support and the unchanged uniqueness outcome;
- `wallFamilyRecoveryUsed` for downstream fixture-source enforcement.

No private image path, task identity, filename, manual label or target angle appears in the diagnostic.

## Failure Semantics

- Missing/nonfinite/degenerate pair evidence: pair is not equivalent.
- Comparable distinct physical families: `wall_family_ambiguous`.
- No eligible physical family: `wall_family_not_found`.
- Any downstream physical/source/fixture/quality failure remains authoritative.
- Photometric source-consistency magnitude failures can be overridden only by `source-consistency-adjudication/3` after verified radial U-contour and fixture-source evidence; structural/profile failures cannot be overridden.
- Invalid/ambiguous results retain null pose, correction, direction, mechanical and PLC command fields; PLC remains non-authoritative.

## Compatibility

- Omitted feature and explicit v1 execute the existing v1 path unchanged; v2 also preserves an already-unique v1 representative and activates radial family recovery only when v1 cannot decide.
- v2 requires compatible single-groove, refinement-v2 and bundled runtime dependencies.
- Top-level slot-pose result schema and coordinate contract do not change.
