# Runtime Contract: Source Consistency Adjudication v1

## Configuration

The optional detector block is `source_consistency_adjudication`:

```json
{
  "schema_version": "source-consistency-adjudication/1",
  "enabled": false,
  "threshold_version": "endpoint-structure-runtime-adjudication-v1",
  "development_only": true,
  "max_endpoint_structure_difference": 0.05
}
```

Absence or `enabled=false` is byte-semantic legacy behavior: the adjudicator is not called and no adjudication
diagnostic is added. Enabling is valid only for `single_real_groove`, source-consistency enabled and groove-refinement
v2. The block contains no image identity, fixed angle, human truth or PLC parameter.

## Diagnostic output

When enabled, `diagnostics.sidewallSourceConsistencyAdjudication` and the selected refinement's
`sourceConsistencyAdjudication` contain:

```json
{
  "schemaVersion": "source-consistency-adjudication/1",
  "thresholdVersion": "endpoint-structure-runtime-adjudication-v1",
  "enabled": true,
  "developmentOnly": true,
  "authoritative": false,
  "productionDefaultAllowed": false,
  "plcAllowed": false,
  "manualTruthAppliedAtRuntime": false,
  "decision": "ACCEPTED_OVERRIDE",
  "originalStatus": "rejected",
  "effectiveStatus": "accepted",
  "originalFailedChecks": ["edge_contrast_asymmetry"],
  "metrics": {"endpointStructureDifference": 0.02},
  "checks": [],
  "failedChecks": [],
  "imagePoseReleaseAllowed": true
}
```

The original `sourceConsistency` object remains unchanged. `imagePoseReleaseAllowed=true` permits only the existing
image-frame measurement/guidance chain to continue. It never authorizes `mechanicalCorrectionDeg`, `plcCommand`, PLC
I/O or a production-default configuration.

## Decision truth table

| Original/evidence | Decision | Effective status | Image pose |
|---|---|---|---|
| accepted | NOT_NEEDED | accepted | unchanged legacy success |
| rejected, exact contrast-only, every non-contrast check passed, strict endpoint structure passed | ACCEPTED_OVERRIDE | accepted | may continue if every other gate passes |
| rejected but any required check fails | REJECTED | rejected | null/fail-closed |
| missing, malformed or non-finite evidence | NOT_EVALUATED | not_evaluated | null/fail-closed |

Check ordering is canonical and the exact original failure set is compared without accepting unknown values.
