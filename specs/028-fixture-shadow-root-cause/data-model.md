# Data Model: Fixture-Shadow Root-Cause Recovery

## 1. Provisional recognition candidate

`ProvisionalRecognitionCandidate` retains the raw candidate, complete original assessment, original failed checks, recovery eligibility checks and a non-authoritative disposition. Eligibility requires exact width-variation-only rejection and every other original recognition check passing. It cannot release pose directly.

## 2. Per-radius wall-edge candidates

`WallEdgeCandidateSet` contains one radial sample identity, radius, bounded polarity-correct edge candidates and missing/overflow status. Each edge candidate records observed position, angle, contrast, gradient and local profile evidence. Ordering is deterministic and not a semantic rank.

## 3. Wall family hypothesis

`WallFamilyHypothesis` records family ID, observed supporting rows/points, support ratio, longitudinal coverage, line residual P95, circle intersection, coarse-boundary delta and failed checks. State is `qualified`, `rejected`, or `ambiguous`; exactly one qualified family is required per wall.

## 4. Effective source decision

`EffectiveSourceDecision` preserves `originalStatus`, `originalFailedChecks`, original metrics/checks, strategy version, independent adjudication checks and `effectiveStatus`. An accepted override is possible only for exact contrast-only rejection with all non-contrast original checks passing. Structural failures can never be overridden.

## 5. Groove/source classification

Classification values are:

- `REAL_GROOVE_COMPLETE_VISIBLE`
- `REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW`
- `REAL_GROOVE_SHADOW_MIXED_OR_OCCLUDED`
- `INDETERMINATE`

The classification includes selected candidate ID, effective survivor count, nearby/overlap evidence, original/effective decisions and terminal stage. It does not itself bypass any global/upstream quality failure.

## 6. Observed replay transition

Each frozen image transition stores image SHA, physical sample ID, old result, new result, terminal stage, classification, evidence availability, safety-null status and timing. Aggregation is by both frame and physical group and marks `eligibleForIndependentAcceptance=false`.

## 7. State transitions

```text
raw rejected by multiple/hard checks -> rejected
raw rejected only by width variation -> provisional
provisional + zero wall-family survivors -> rejected
provisional + multiple wall-family survivors -> ambiguous
provisional + unique two-wall geometry + structural source pass -> effective survivor
original source accepted -> effective source accepted
original source contrast-only rejected + all structural checks pass -> accepted override
any structural source failure -> mixed/occluded or indeterminate, fail closed
exactly one effective candidate + all global gates pass -> pose eligible
zero/multiple effective candidates or upstream/global failure -> no pose
```
