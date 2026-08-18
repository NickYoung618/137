# Research: Circle-Family Consensus Stabilization

## Decision 1: Treat the defect as intra-family representative bias

**Decision**: Keep the current hypothesis generation and family grouping. Under version 2, preserve a grouped-family representative that already satisfies the existing authoritative residual gate; otherwise replace only that representative with bounded consensus and reassignment.

**Rationale**: Both failing frames have one qualified family, high support and coverage. Reassigning the same observed candidates reduces final P95 from 5.451/5.487 px to 2.819/2.842 px without changing thresholds. About 91–93 common rays change adjacent edge layer under the biased representative. Applying the correction to an already-qualified 3.395 px family moved its circle by only about 0.1 px but changed a downstream occluded-groove wall vote from ambiguous to accepted. The existing residual gate therefore provides the stage boundary: correct a representative that would already fail, but do not perturb one that is already authoritative.

**Alternatives considered**: Raising residual or sector limits was rejected because it weakens safety. Fixture-sector exclusion was rejected as the decisive explanation because the changed assignments are distributed broadly and the same images pass without excluding sectors. Replacing the edge primitive was rejected because the needed candidates already exist.

## Decision 2: Consolidate only inside an existing group and require convergence

**Decision**: Build a deterministic finite seed from all member circles of one grouped family, assign one observed candidate per ray, refit, and repeat to identical assignment or a fixed small iteration cap. A non-convergent family is ineligible.

**Rationale**: This removes dependence on the first sorted member while retaining the existing boundary between distinct physical families. Stable assignment is stronger evidence than merely averaging parameters.

**Alternatives considered**: Averaging all families was rejected because it can hide ambiguity. Selecting the sparse circle directly was rejected because final evidence must decide independently. Selecting the lowest final residual among member hypotheses was rejected because it adds winner-shopping rather than one family consensus. Running correction unconditionally was rejected because it can needlessly alter a downstream fail-closed decision after the original circle already passed.

## Decision 3: Use observed points only and preserve authoritative fitting

**Decision**: Consensus may select only candidates already extracted on each ray. Its preliminary refit uses the current bounded algebraic circle mechanism; the existing `robust_fit_circle` remains the single authoritative final fit.

**Rationale**: This preserves provenance and the established unique-family-to-authoritative-fit chain while avoiding interpolation or repeated expensive robust fits.

**Alternatives considered**: Interpolating missing rays and robust-fitting every member were rejected for evidence integrity and latency.

## Decision 4: Version 2 is opt-in and diagnostics are additive

**Decision**: Accept both `deterministic-three-point-global-circle-v1` and `deterministic-family-consensus-circle-v2`. Version 1 follows the old path. Version 2 adds nested consensus summaries without changing the root result schema.

**Rationale**: Frozen 026/028 configurations remain reproducible, while Mac replay identifies the exact new behavior.

**Alternatives considered**: Silently changing version 1 was rejected as unauditable. A new top-level result schema was rejected because diagnostics are intentionally extensible.

## Decision 5: Freeze gates and validate in layers

**Decision**: Keep all existing thresholds unchanged. Validate synthetic invariance/safety first, then frames 442/449, the other 138 observed frames, six-image 026 compatibility, repeatability, schemas and warm performance.

**Rationale**: This directly distinguishes algorithm correction from threshold tuning and protects the 41 reviewed mixed/occluded groove failures.

**Alternatives considered**: Optimizing against the later 700 images was rejected; they are already observed and may only be a frozen diagnostic replay.
