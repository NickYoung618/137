# Data Model

## Representative Case

- imageId、sampleId、SHA、relativePath
- expectedDiagnosticClass（不是人工真值）
- errorCode、failureStage、finalValid
- circle/candidate/groove/refinement/sourceConsistency evidence
- overlayPath（Git外）
- humanReviewStatus

## Root Cause Decision

- observedFailure、causalEvidence、counterexample
- reusableSource（yyh/gyj/现有slot_pose）
- safeToImplement、humanEvidenceRequired
- regressionScope

## Legacy Core Source

- `sourceMode`: `bundled_module` or backward-compatible `external_file`
- `bundledModule`: fixed repository module identity when bundled
- `sourceSha256`: bytes of the actually loaded local/external source
- `upstreamSourceSha256`: reviewed gyj provenance; diagnostic provenance only
- annotation/reference paths and hashes: Git-external deployment assets, independent from source-code ownership
