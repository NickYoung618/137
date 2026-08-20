# Research: Physical-Groove Polar Quality Adjudication

## Decision 1: Treat the legacy polar value as global registration evidence, not groove identity

**Decision**: Preserve the score and threshold unchanged, but permit an independent effective-quality decision only after the refined groove itself has supplied complete physical pose evidence.

**Rationale**: The observed 20-frame sequence has one unique accepted groove, accepted refinement/source evidence and a 5/5 curved floor, while only the whole-ring polar score is 0.072–0.155 below threshold. The pose in single-real-groove mode already comes from refined groove geometry, not polar rotation.

**Alternatives considered**: Lowering `min_polar_score`, clamping the score, or using the polar rotation in pose were rejected because they weaken unrelated modes, erase evidence or change the pose source.

## Decision 2: Require the existing complete physical proof chain

**Decision**: Require one accepted physical circle/edge family, one accepted groove, accepted two-wall refinement with finite endpoints, accepted 5/5 curved floor, accepted effective source consistency and verified fixture-source exclusion.

**Rationale**: These checks are already computed from image geometry and distinguish the observed complete groove from known fixture-mixed or occluded cases. Reusing them adds no analysis pass.

**Alternatives considered**: Candidate score alone, runtime classification alone, fixture distance, fixed angular sectors and observed image identity were rejected as insufficient or sample-specific.

## Decision 3: Override only an exact sole failure

**Decision**: The eligible original failure list must be exactly `['polar_score']`. Scale, ambiguity, recognition, refinement, source, fixture and every other quality failure remain authoritative.

**Rationale**: Exact matching makes the exception narrow, testable and fail-closed. It prevents a good groove shape from masking a separate input or registration problem.

**Alternatives considered**: Removing polar from an arbitrary failure set or allowing a configurable list of bypasses were rejected as unsafe scope expansion.

## Decision 4: Separate original and effective states

**Decision**: Never mutate `quality.failedChecks`. Emit a separate versioned adjudication containing original failures, effective failures, ordered proof checks, decision and pose-release permission.

**Rationale**: Reviewers must see that the score failed even when image pose proceeds. This also preserves compatibility for consumers that audit original quality evidence.

**Alternatives considered**: Deleting `polar_score` in place or marking the original quality as passed were rejected because they destroy provenance.

## Decision 5: Keep the feature default-off and single-mode

**Decision**: Omitted/disabled config preserves prior behavior. Enabling is legal only in single-real-groove mode with compatible physical-circle, refinement, source, fixture and shadow diagnostics.

**Rationale**: Other modes may use polar rotation for role or pose logic and cannot safely share this exception. Explicit dependency checks prevent partial configurations.

**Alternatives considered**: Global enablement and reuse in legacy notch or multi-role modes were rejected.

## Decision 6: Do no additional image work

**Decision**: Evaluate a fixed set of existing finite diagnostic fields after the physical chain; perform no image load, polar resampling, circle fit, candidate extraction or refinement.

**Rationale**: The original 700 replay exposed server first-pass performance pressure. A constant-size pure decision avoids worsening it and is deterministic.

**Alternatives considered**: Recomputing a local polar score or adding a new image mask in the first implementation were rejected because existing U-contour evidence already answers the safety question with less complexity.

## Decision 7: Keep observed data diagnostic-only

**Decision**: Use the 20-frame sequence to prove the root-cause transition, the 24 valid frames as positive compatibility and the 174 mixed/occluded frames as safety regression. Require new physical parts before accuracy claims.

**Rationale**: All 700 frames have already been reviewed diagnostically and cannot serve as unseen acceptance.

**Alternatives considered**: Reporting 20 independent corrections or production accuracy from the replay was rejected.
