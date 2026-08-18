# Research: Sidewall Family Deduplication

## Decision 1: Prove same-source identity over shared observed geometry

**Decision**: A v2 hypothesis pair is equivalent only when it has sufficient shared observed support/span and passes finite direction, shared-span position and outer-circle endpoint checks together.

**Rationale**: Current v1 deduplicates on endpoint angle or candidate-signature overlap. Initial diagnostics showed `bad-0102` top supports 25/24 and endpoint angles separated by about 0.163°. Full shared-span comparison then proved these two lines diverge by about 9.06° and up to about 10.30 px: they must remain distinct rather than be falsely merged.

**Alternatives considered**: Increasing the v1 endpoint angle, using support/order/signature alone, or changing the ambiguity margin were rejected because none proves common physical origin and each weakens a global decision.

## Decision 2: Compare finite shared spans, not infinite line coefficients

**Decision**: Canonical directions define a stable common longitudinal axis. Each line's actual selected points define its observed interval. Only the interval intersection is compared, using signed start/mid/end separation plus bounded aggregate separation.

**Rationale**: Infinite-line distance hides crossings and `(a,b,c)` comparison depends on sign/origin. Shared-span endpoints expose divergence while allowing a sufficiently observed noisy subset.

**Alternatives considered**: Global nearest distance, coefficient deltas and endpoint angle alone were rejected as incomplete geometric evidence.

## Decision 3: Complete-link families with observed representatives

**Decision**: Merge two groups only when every cross-group pair is equivalent. Choose one existing hypothesis deterministically; do not sum duplicate support or refit/average a new line.

**Rationale**: Complete-link prevents the transitive bridge `A≈B`, `B≈C`, `A≉C`. Keeping an observed representative preserves the meaning of current residual and endpoint gates.

**Alternatives considered**: Connected components/single-link and family refitting were rejected because they can over-merge or invent an unobserved wall.

## Decision 4: Add explicit v2 configuration and internal diagnostic versions

**Decision**: Preserve `groove-wall-edge-family/1` + `bounded-cross-radius-wall-family-v1`. Add a strict, explicit v2 schema/strategy, internal refinement diagnostic v4, and a strict wall-source-family diagnostic schema. The top-level result schema stays unchanged because diagnostics are open.

**Rationale**: Existing configs and portable profiles must remain reproducible. The diagnostic meaning changes materially even though output pose/null semantics do not.

**Alternatives considered**: Mutating v1 in place or globally enabling v2 were rejected as unauditable compatibility breaks.

## Decision 5: Preserve the complete fixture/U-contour safety chain

**Decision**: Replace the adapter's exact v1 strategy-string check with explicit supported recovery evidence so both v1 and v2 require fixture verification, two walls, curved floor and source exclusion.

**Rationale**: Merely adding a new strategy string would otherwise bypass the safety check. Family deduplication corrects identity counting only; it cannot overrule source consistency or occlusion evidence.

**Alternatives considered**: Case-specific adapter recovery and using fixture proximity as an automatic decision were rejected.

## Decision 6: Treat corrected cases as observed regressions only

**Decision**: Bind `bad-0015` and `bad-0102` by their exact task IDs and image hashes in Git-external reports. Use them to verify root-cause transitions and safety nulls, not to claim accuracy.

**Rationale**: The 700-image A2 set has already been inspected. A physically separate new-part group is required for acceptance.

**Alternatives considered**: Counting these cases or the 700 frames as unseen acceptance was rejected.

## Decision 7: Require housing-radial wall ownership before uniqueness

**Decision**: Preserve the prior v1 representative whenever v1 already has a unique winner. When v1 is ambiguous/not-found, each v2 physical source-family representative must align with the radius joining the fitted housing center to its own outer-circle intersection. Non-radial fixture/machining responses remain diagnosed but are ineligible for the v2 recovery gate; absence of radial evidence falls back to the prior v1 fail-closed result.

**Rationale**: In corrected `bad-0102`, the higher-support false response was about 12° from radial while the physical wall was about 3.3° from radial. This relation is image-derived, rotation invariant and independent of filename, target angle or fixed fixture angle. The 140-frame compatibility replay also showed that making radial alignment mandatory for already-successful v1 recoveries changed eight established representatives, so v2 must be an additive recovery rather than a replacement.

**Alternatives considered**: Widening the merge distance, choosing the outermost/strongest response and fixed angular masks were rejected because they either merge distinct sources or encode the observed sample.

## Decision 8: Release photometric asymmetry only behind complete geometric proof

**Decision**: Add source-adjudication v3. It can override only contrast/gradient magnitude failures after two radial sidewalls, a five-track curved floor, verified fixture bodies, fixture-source exclusion, normalized-profile similarity, radial coverage and endpoint structure all pass. The original v1 source-consistency result is retained unchanged.

**Rationale**: Corrected `bad-0102` has normalized profile correlation about 0.974 and all structural checks pass, but asymmetric illumination changes absolute contrast and gradient. Corrected `bad-0015` lacks a complete second wall/U contour and therefore cannot reach this override.

**Alternatives considered**: Raising global source thresholds, ignoring lower fixture overlap, or accepting any U-like dark region were rejected because they weaken unrelated samples and could release true occlusion or fixture sources.
