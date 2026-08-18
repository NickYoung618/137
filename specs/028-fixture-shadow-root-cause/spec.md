# Feature Specification: Fixture-Shadow Root-Cause Recovery

**Feature Branch**: `028-fixture-shadow-root-cause`

**Created**: 2026-08-18

**Status**: Draft

**Input**: Diagnose and repair the observed A2 single-shot failures without lowering global gates, while retaining fail-closed behavior for truly mixed or occluded groove evidence.

## User Scenarios & Testing

### User Story 1 - Recover complete visible grooves (Priority: P1)

As the inspection owner, I need a complete physical groove to remain measurable when nearby fixture shadow or uneven illumination changes one wall's appearance, so normal parts are not rejected merely because the two walls have different absolute contrast.

**Why this priority**: The 140-frame observed replay contains repeatable false rejections at recognition, wall refinement, and source-consistency stages.

**Independent Test**: Freeze the 140 listed image hashes and replay the feature configuration once. Every release must be supported by one unique physical groove whose two sidewalls and outer-circle endpoints are geometrically coherent; no release may rely only on a relaxed scalar threshold.

**Acceptance Scenarios**:

1. **Given** a complete groove with unequal wall brightness but matching normalized edge shape, endpoint structure, radial coverage and physical opening geometry, **When** the image is evaluated, **Then** the system accepts the unique physical groove and records the original failed gate plus the independent recovery evidence.
2. **Given** a coarse groove whose width varies near a fixture shadow, **When** all other recognition checks pass and downstream physical wall evidence is unique and complete, **Then** it may be recovered without changing the original recognition threshold.
3. **Given** a wall whose outermost samples are contaminated but whose interior trace uniquely reaches the physical circle, **When** endpoint recovery is evaluated, **Then** the system uses bounded image-derived geometric evidence or fails closed.

---

### User Story 2 - Reject shadow and occlusion safely (Priority: P1)

As the safety owner, I need fixture shadows, competing dark regions, and genuinely mixed or occluded groove walls to remain non-authoritative, so an apparently plausible angle cannot reach guidance or PLC fields.

**Why this priority**: A recovery path that merely increases acceptance would violate the project safety contract.

**Independent Test**: Synthetic and real observed negative cases exercise missing walls, competing survivors, structurally dissimilar wall profiles, nonfinite evidence and upstream failure. Each case must remain invalid with all pose and PLC command fields empty.

**Acceptance Scenarios**:

1. **Given** two physical candidates survive all independent checks, **When** the image is evaluated, **Then** the result is explicitly ambiguous and no angle is released.
2. **Given** a real wall is mixed with or occluded by shadow such that structural, endpoint, coverage, or geometric evidence is missing or inconsistent, **When** recovery is evaluated, **Then** it is rejected with the failed evidence named.
3. **Given** only absolute contrast differs while all independent structure checks pass, **When** classification is produced, **Then** the sample is not labelled mixed or occluded solely because of contrast asymmetry.

---

### User Story 3 - Preserve circle and compatibility behavior (Priority: P2)

As the algorithm maintainer, I need the two observed outer-circle residual failures explained and bounded without weakening the accepted circle family, and I need configurations that omit the feature to remain unchanged.

**Why this priority**: Two of 140 frames fail before groove processing, while the already accepted 026 behavior is a compatibility baseline.

**Independent Test**: Replay the two failing frames and the six-image 026 regression set with frozen hashes. Any recovery must retain one unique physical circle family, existing quality gates and default-off equivalence.

**Acceptance Scenarios**:

1. **Given** a unique edge family with a localized residual sector caused by the physical opening, **When** the existing bounded sector robustness evidence is sufficient, **Then** the circle may be refit once and must still satisfy the original final quality gates.
2. **Given** multiple eligible circle families or excessive residual outside the bounded sector policy, **When** localization runs, **Then** it remains failed or ambiguous.
3. **Given** a configuration that omits the new recovery feature, **When** it runs, **Then** its effective identity and outputs remain equivalent to the prior committed behavior.

### Edge Cases

- No raw groove candidate is generated, versus raw candidates exist but all fail recognition.
- Exactly one hard gate fails, multiple gates fail, or evidence is missing/nonfinite.
- A provisional recognition candidate and a normal accepted candidate both survive downstream checks.
- A straight-wall model is unstable but a bounded radial trace is unique; multiple trace models remain ambiguous.
- A source-consistency payload is accepted, contrast-only rejected, or rejected by any structural check.
- The groove opening overlaps a circle sector excluded by robustness; excluded span or circle shift exceeds its locked bound.
- Repeated frames from one physical part must not be counted as independent parts.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST distinguish raw candidate absence from raw candidate rejection and record the terminal stage and failed checks.
- **FR-002**: The system MUST preserve every original recognition, refinement, source-consistency and circle gate result as immutable diagnostic evidence.
- **FR-003**: The system MUST NOT lower the global ambiguity, groove recognition, groove refinement, polar quality, source-consistency, or physical-circle thresholds to recover the observed set.
- **FR-004**: A recognition recovery MUST be limited to an explicitly versioned, bounded provisional state and MUST require unique downstream physical sidewall, endpoint and source evidence before pose release.
- **FR-005**: Source recovery MUST require contrast-only original rejection plus passing normalized profile shape, gradient, radial coverage, endpoint structure and geometric checks; contrast asymmetry alone MUST NOT classify a groove as mixed or occluded.
- **FR-006**: Endpoint recovery MUST use image-derived sidewall observations, produce bounded residual/support/coverage/uniqueness evidence, and reject missing, nonfinite or multiple eligible models.
- **FR-007**: Candidate selection MUST be invariant to filename, sample identity, fixed angle, target angle, candidate order and manual truth.
- **FR-008**: A pose MAY be released only when exactly one candidate survives all required stages; zero survivors MUST fail explicitly and multiple survivors MUST be ambiguous.
- **FR-009**: Truly mixed or occluded wall evidence MUST remain fail-closed; invalid or ambiguous results MUST have null angle, direction, correction and PLC command fields and non-authoritative PLC status.
- **FR-010**: Circle recovery MUST retain the unique edge-family decision, bounded sector policy and unchanged final circle quality gates; it MUST NOT select by the observed image identity.
- **FR-011**: Runtime diagnostics MUST record original/effective decisions, evidence origin, candidate disposition, terminal stage, recovery checks, numeric margins and strategy/schema versions.
- **FR-012**: New behavior MUST be default-off and existing omitted configurations, external modules and 026 regression behavior MUST remain compatible.
- **FR-013**: The 140-frame set MUST be treated only as an already-observed development regression set; reports MUST group by seven physical parts and MUST NOT call it independent acceptance.
- **FR-014**: The implementation MUST include unit, contract, synthetic ambiguity/occlusion, static-repeatability, performance and frozen real-image regression tests.
- **FR-015**: The implementation MUST NOT access sealed part-006, modify PLC/HMI, merge main, or authorize production/PLC use.
- **FR-016**: The later 700-frame replay MUST use frozen code/config and remain diagnostic; production accuracy claims require a physically separate acceptance set.
- **FR-017**: Fixture context MAY use the stationary upper-small/lower-large circular bodies only through a versioned image-derived calibration that is re-detected and uniquely verified in every frame. It MUST NOT assume a fixed angle, treat the calibrated sector as an automatic rejection zone, or release pose without independent complete U-contour groove evidence.
- **FR-018**: The stationary lower-large fixture body MUST be treated only as a possible false-candidate source and MUST NOT be labelled as groove occlusion. Only overlap with the upper-small body MAY carry an occlusion or shadow-mixing risk; a complete groove near that upper body still requires independent two-wall plus curved-floor U-contour evidence.

### Key Entities

- **Recovery Candidate**: One coarse dark-region hypothesis with its original recognition decision and optional provisional state.
- **Wall Trace Evidence**: Image-derived sidewall observations, model support, coverage, residual, endpoint and uniqueness result.
- **Source Adjudication Evidence**: Immutable original source-consistency result plus independent structural checks and effective decision.
- **Observed Regression Cohort**: Frozen image hashes, physical part grouping, prior/new outcomes and non-acceptance data-use designation.
- **Recovery Diagnostic**: Versioned per-image record of candidates, original/effective gates, terminal stage, release authority and timing.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All 140 frozen images are accounted for exactly once, grouped as seven physical parts of twenty frames, with zero hash mismatches and zero unexplained terminal stages.
- **SC-002**: Every image visually confirmed as a complete visible groove in the observed cohort has exactly one evidence-complete survivor; any retained rejection is linked to explicit mixed/occluded, ambiguous, upstream, or insufficient-evidence review status.
- **SC-003**: All synthetic and reviewed mixed/occluded cases remain invalid, and 100% of invalid/ambiguous outputs have null pose, correction, direction and PLC command fields.
- **SC-004**: The sixteen observed part-008 prior-valid frames have no source-consistency regression caused solely by absolute contrast asymmetry.
- **SC-005**: The twenty part-015 frames are reported as generated-but-rejected candidates, and any recovery requires successful downstream physical evidence rather than a changed width-variation limit.
- **SC-006**: The forty part-009/part-021 refinement failures either gain unique bounded endpoint evidence or remain explicitly rejected; no fallback fabricates an endpoint.
- **SC-007**: The two part-023 outer-circle cases pass only if they satisfy the unchanged final quality gates after the existing bounded robustness process; otherwise their failure remains explicit.
- **SC-008**: Five repeated runs per representative recovered and rejected case produce identical status, selected candidate, geometry and diagnostic counts.
- **SC-009**: Reused-adapter warm performance remains at or below 2.5 seconds P95 per image on the current server.
- **SC-010**: Default-off 026 real-image outputs and effective config identity remain unchanged, and focused tests plus all root schemas pass.
- **SC-011**: The final report clearly states that 140 and the later 700 are observed diagnostics, not production accuracy evidence, and PLC remains unauthorized.
- **SC-012**: Across all seven observed physical groups, fixture-body evidence either uniquely verifies the two-body geometry in-frame or reports not-evaluated; rotating synthetic scenes preserves the same relative classification, the lower body is never classified as occlusion, and no candidate is selected or rejected from absolute fixture angle alone.

## Assumptions

- The 140-image manifest and image hashes are immutable and contain seven user-confirmed physical groups; the folder class `normal` is not by itself human truth for groove visibility.
- Visual review may establish development expectations, but any uncertain frame remains fail-closed until the owner supplies a label.
- Existing 026 circle-family selection, recognition, refinement, source-consistency and ambiguity results remain authoritative evidence even when an independent recovery decision is added.
- The later 700 images will be replayed only after upload integrity and image hashes are verified.
