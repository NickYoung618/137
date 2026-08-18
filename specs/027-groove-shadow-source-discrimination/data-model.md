# Data Model: Groove Shadow Source Discrimination

## 1. Runtime configuration

### `GrooveShadowSourceDiscriminationConfig`

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | exactly `groove-shadow-source-discrimination/1` |
| `enabled` | boolean | default `false` |
| `strategy_version` | string | exactly `physical-sidewall-source-evidence/1` |

No numeric threshold is owned by this object. Enabling requires the existing ambiguity resolver, v2 groove refinement and original sidewall source-consistency to be enabled.

## 2. Candidate source evidence

### `CandidateSourceEvidence`

Bounded to the existing ambiguity capacity of three.

| Field | Type | Meaning |
|---|---|---|
| `candidateId` | opaque string | Diagnostic correlation only; never used for ordering/selection |
| `coarseRecognition` | evaluation | Existing accepted/failed/not-evaluated state and failed checks |
| `coarseMetrics` | object/null | Width, contrast, radial depth, paired support, continuity, drift, outer connection |
| `physicalRefinement` | evaluation | Existing v2 refinement accepted/failed/not-evaluated |
| `sidewallEvidence` | object/null | Independent walls, consensus, residual/span, endpoints and circle intersections |
| `sourceConsistency` | evaluation | Original sidewall source-consistency accepted/failed/not-evaluated |
| `sourceMetrics` | object/null | Existing contrast/gradient/profile/coverage/endpoint differences |
| `sourceDisposition` | enum | `REAL_GROOVE_SURVIVOR`, `NON_GROOVE_SOURCE_REJECTED`, `MIXED_OR_OCCLUDED_EVIDENCE`, `INDETERMINATE` |
| `failedChecks` | string[] | Stable existing check identifiers, bounded and de-duplicated |

An evaluation has status `accepted`, `failed`, or `not_evaluated`. Missing and non-finite values can never become `accepted`.

## 3. Runtime disposition

### `GrooveShadowDisposition`

| Field | Type | Meaning |
|---|---|---|
| `schemaVersion` | string | `groove-shadow-source-diagnostic/1` |
| `strategyVersion` | string | `physical-sidewall-source-evidence/1` |
| `enabled` | boolean | Effective config state |
| `status` | enum | `disabled`, `accepted`, `rejected`, `not_evaluated` |
| `classification` | enum/null | Requested three-state classification; null while disabled/upstream unavailable |
| `terminalStage` | enum | Normalized failure/valid stage |
| `poseChainAllowed` | boolean | True only when this discriminator and every pre-existing gate allow continuation |
| `selectedCandidateId` | string/null | Unique physical survivor, if any |
| `candidateCount` | integer | Total coarse candidates observed |
| `candidateEvidence` | array | At most three `CandidateSourceEvidence` items |
| `passedChecks` | string[] | Stable decision checks |
| `failedChecks` | string[] | Stable decision failures |
| `lockedGateVersions` | object | Recognition/refinement/source/ambiguity versions used |

### State transitions

```text
disabled -> status=disabled, classification=null, poseChainAllowed=legacy decision
upstream unavailable -> not_evaluated + INDETERMINATE + fail closed
evidence missing/nonfinite/overflow -> rejected + INDETERMINATE + fail closed
multiple survivors -> rejected + INDETERMINATE + fail closed
zero survivors + explicit mixed wall/source evidence -> rejected + MIXED_OR_OCCLUDED + fail closed
one survivor + every competitor explicitly rejected -> accepted + COMPLETE_NEAR_SHADOW
accepted local disposition + any original/global failure -> rejected terminal result; no pose release
```

## 4. Offline failure trace

### `FailureTrace`

| Field | Type | Meaning |
|---|---|---|
| `imageSha256` | 64-char hex | Join key across failure index and JSONL |
| `taskId` | string | Audit identity only; never runtime input |
| `sourceCohort` | enum | `observed-diagnostic` or `independent-acceptance` |
| `originalErrorCode` / `originalStage` | string/null | Frozen result values |
| `terminalStage` | enum | Normalized stage |
| `candidateCounts` | object | generated/recognized/refined/source-accepted counts where available |
| `candidateEvidenceAvailability` | enum | `complete`, `partial`, `not_evaluated` |
| `humanSemanticClass` | enum/null | Offline-only, null for uploaded 700 unless a frozen per-image label exists |
| `runtimeDisposition` | object/null | Runtime nested diagnostic when feature was enabled |
| `safetyOutputsNull` | boolean | Required true for invalid results |
| `overlayStatus` | enum | `available`, `indexed_existing`, `unavailable` |

## 5. Cohorts

### `ObservedDiagnosticCohort`

Contains the frozen A2 report/archive SHA, configuration SHA, results SHA(s), 700 image SHA keys, and an explicit `eligibleForAcceptance=false`. It may support root-cause counts but never accuracy or unseen claims.

### `IndependentAcceptanceCohort`

Requires a frozen manifest with physical part IDs, image SHA, offline human class and group provenance. Validation requires no physical ID overlap with the observed cohort, no sealed part-006, frozen code/config before truth unsealing, and separate results for complete-near-shadow versus mixed/occluded.

## 6. Trust boundary

`humanSemanticClass`, file paths, task IDs and cohort membership exist only in offline reports. The runtime disposition function accepts only bounded candidate evidence and pre-existing gate outcomes; its type and tests prevent annotations or filenames from entering selection.
