# Data Model: Revocation and Registration Diagnostics

## RevokedReference

- `annotationSha256`: path-independent prohibited fingerprint
- `reasonCode`: stable machine-readable revocation reason
- `scope`: template, tuning, truth, and acceptance use

The entity is an input safety rule; it is never an evidence record.

## ReferenceHousingSelection

- `hypothesisCount`: supported, deduplicated physical instances
- `selectedCenterPx`, `selectedRadiusPx`
- `runnerUpRadiusPx`: null when no runner-up exists
- `radiusMarginRatio`
- `minimumRadiusMarginRatio`
- `valid`, `failureReason`

No annotation label or endpoint field is allowed.

## RegistrationDiagnosticRecord

- `schemaVersion`, `technicalStatus`, `error`
- `input.referenceImage`, `input.targetImage`: path, SHA-256, dimensions
- `algorithm`: registration version, immutable core SHA-256, and config SHA-256
- `registration`: hypotheses, selected instance, transform, checks

Forbidden fields: `candidateValid`, `transition`, `recovered`, measurements,
`coreValid`, localization, and measurement completeness.

## RegistrationBatchSummary

- total/succeeded/failed record counts
- registration valid/invalid counts
- failure-reason distribution
- reference/config fingerprints
- diagnostic JSONL fingerprint

## State transitions

- Corrected/unknown fingerprint → structural validation may continue.
- Revoked fingerprint → terminal rejected state before parsing.
- Registration valid with no corrected truth → diagnostics allowed; candidate acceptance blocked.
