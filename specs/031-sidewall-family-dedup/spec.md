# Feature Specification: Sidewall Family Deduplication

**Feature Branch**: `031-sidewall-family-dedup`

**Created**: 2026-08-19

**Status**: Draft

**Input**: Correct a false refinement ambiguity and downstream source rejection in which fixture/machining responses compete with a complete visible physical groove near the fixed bodies, without weakening any existing quality gate or releasing mixed/occluded grooves.

## User Scenarios & Testing

### User Story 1 - Recover a complete visible groove near fixtures (Priority: P1)

As the inspection owner, I need multiple image responses belonging to one physical sidewall to be treated as one source, so a complete visible groove is not rejected merely because machining texture or nearby fixture contrast creates several almost coincident line hypotheses.

**Why this priority**: Corrected evidence for `bad-0102` shows a complete U-shaped opening and five accepted floor tracks. Detailed v2 tracing proved that its two strongest start-wall responses are distinct: one is non-radial fixture/machining evidence, while the physical groove wall follows the housing-radius geometry. After resolving that ambiguity, old coarse fixture-sector overlap and absolute photometric asymmetry still reject an otherwise consistent normalized U contour.

**Independent Test**: Supply bounded synthetic row candidates containing several noisy responses from one physical line. The result has exactly one geometric source family, is invariant to candidate ordering, and preserves a deterministic representative line.

**Acceptance Scenarios**:

1. **Given** several fitted hypotheses that remain geometrically coincident over their shared observed span and reach the same bounded outer-circle endpoint, **When** wall-family uniqueness is evaluated, **Then** they form one physical source family rather than an ambiguity.
2. **Given** one complete visible groove near, but not mixed with, the stationary fixture bodies, **When** both wall sources and the curved floor are independently complete, **Then** fixture proximity alone does not reject the groove.
3. **Given** two walls whose directions agree with their housing-circle endpoint radii, a complete curved floor, verified fixture bodies and consistent normalized wall profiles, **When** only absolute contrast/gradient magnitude differs under illumination, **Then** a versioned non-authoritative adjudication may preserve the original rejection evidence and release image pose.

---

### User Story 2 - Preserve fail-closed separation and occlusion behavior (Priority: P1)

As the safety owner, I need genuinely distinct wall sources and fixture-mixed or occluded walls to remain rejected, so deduplication cannot convert uncertainty into an authoritative angle.

**Why this priority**: Corrected evidence for `bad-0015` contains a wall touching the upper fixture and has large contrast/gradient asymmetry plus inconsistent endpoint structure; that rejection must not regress.

**Independent Test**: Supply two parallel or crossing physical lines with comparable support, plus missing-wall and nonfinite cases. None may be collapsed solely because their scores, candidate indices, or endpoints are close.

**Acceptance Scenarios**:

1. **Given** two line hypotheses that diverge materially anywhere over their shared physical observation span, **When** family uniqueness is evaluated, **Then** they remain separate and comparable survivors cause an explicit ambiguity.
2. **Given** a groove wall mixed with or hidden by the upper fixture, **When** sidewall, endpoint, or source evidence is incomplete or inconsistent, **Then** the result remains invalid and all guidance and PLC command fields remain null.

---

### User Story 3 - Produce reviewable and compatible evidence (Priority: P2)

As the algorithm maintainer, I need the family grouping decision to be versioned and explainable while existing configurations retain their prior behavior unless the new strategy is explicitly enabled.

**Why this priority**: The observed 700-image replay is diagnostic data and cannot safely support an opaque behavior change or a production accuracy claim.

**Independent Test**: Validate old and new configurations, inspect per-family diagnostics, repeat representative cases, and verify unchanged outputs for the prior strategy.

**Acceptance Scenarios**:

1. **Given** an existing configuration using the prior strategy, **When** it is loaded and run, **Then** its behavior and accepted fields remain compatible.
2. **Given** the new strategy is enabled, **When** hypotheses are grouped, **Then** diagnostics record original hypothesis count, physical-source-family count, membership, geometric separation evidence, representative identity, and the final uniqueness decision.

### Edge Cases

- Hypotheses share many sampled points but diverge near the housing-circle endpoint.
- Hypotheses have close endpoint angles but represent distinct parallel edges.
- One hypothesis is a strict noisy subset of another physical line.
- A family contains equal-support representatives or input candidates arrive in a different order.
- Shared longitudinal coverage is too small to establish geometric equivalence.
- Coordinates, residuals, or derived distances are missing or nonfinite.
- The groove overlaps multiple fixture bodies but its complete U-contour is or is not independently observable.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST distinguish raw line hypotheses from physical wall-source families before declaring wall ambiguity.
- **FR-002**: Two hypotheses MAY share a physical source family only when bounded image-derived geometry demonstrates equivalent line position across sufficient shared longitudinal coverage and equivalent outer-circle endpoint location.
- **FR-003**: Endpoint proximity, support similarity, candidate order, filename, sample identity, fixed angle, target angle, manual review, and fixture proximity alone MUST NOT establish source equivalence.
- **FR-004**: Hypotheses that materially diverge across their shared span MUST remain separate even if their endpoint angles are close; comparable surviving physical families MUST remain ambiguous.
- **FR-005**: Physical-family grouping and representative selection MUST be deterministic and invariant to candidate and hypothesis ordering.
- **FR-006**: Missing, insufficient, degenerate, or nonfinite equivalence evidence MUST fail closed and MUST NOT merge hypotheses.
- **FR-007**: The selected representative MUST be an observed fitted hypothesis; the system MUST NOT invent or interpolate an unobserved sidewall.
- **FR-008**: The new behavior MUST be explicitly versioned, bounded in work, and compatible with the prior strategy when it is not selected.
- **FR-009**: Diagnostics MUST record hypothesis-to-family membership, comparison metrics and margins, family count, representative, and final failure reason without exposing private paths or manual labels.
- **FR-010**: Existing recognition, refinement residual, source-consistency, curved-floor, ambiguity, polar-quality, and physical-circle thresholds MUST remain unchanged.
- **FR-011**: A complete visible groove near fixtures MAY pass only after two distinct sidewalls, their outer-circle endpoints, and the curved floor are independently complete; fixture proximity alone MUST be non-authoritative.
- **FR-012**: Mixed or occluded evidence such as corrected `bad-0015` MUST remain fail-closed; invalid or ambiguous results MUST contain null angle, correction, direction, mechanical command and PLC command fields, with PLC non-authoritative.
- **FR-013**: The implementation MUST include unit, contract, synthetic same-source/distinct-source, candidate-order, nonfinite, real observed regression, static-repeatability and performance tests.
- **FR-014**: The corrected two-case package and the 700-image A2 replay MUST remain observed diagnostic data and MUST NOT be used as unseen acceptance evidence or to claim production accuracy.
- **FR-015**: Validation MUST use a physically separate new-part group before any accuracy-improvement or production-readiness claim.
- **FR-016**: The work MUST NOT read sealed part-006, modify PLC/HMI, merge main, or authorize PLC operation.
- **FR-017**: The prior v1 representative MUST be preserved when the prior strategy already has a unique winner. Only when v1 cannot decide MAY v2 use a finite rotation-invariant radial-alignment check between fitted direction and housing-circle endpoint radius to make source families eligible; if radial evidence is unavailable, behavior MUST fall back to the prior fail-closed v1 outcome.
- **FR-018**: A coarse candidate overlapping both image-derived fixture sectors MAY exclude fixture source only when two radial sidewalls and an independently accepted curved floor form a complete U contour; lower-fixture proximity alone MUST never be labelled occlusion.
- **FR-019**: A versioned source adjudication MAY override only photometric magnitude failures (`edge_contrast_asymmetry` and/or `edge_gradient_asymmetry`) when all locked normalized-profile, coverage, endpoint-structure, radial-wall, curved-floor and fixture-source checks pass; original evidence MUST remain unchanged.

### Key Entities

- **Wall Hypothesis**: One fitted line with observed row membership, support, residual, span and housing-circle endpoint.
- **Physical Wall-Source Family**: A set of hypotheses proven geometrically equivalent over a bounded shared observation span.
- **Equivalence Evidence**: Finite position, direction, shared-coverage and endpoint comparisons with versioned decision margins.
- **Family Representative**: The deterministically ranked observed hypothesis used by downstream unchanged refinement gates.
- **Observed Diagnostic Case**: Immutable image hash, task ID, runtime JSON and visual evidence used for root-cause regression but not unseen acceptance.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Synthetic variants of one physical wall containing reordered, duplicated and noisy responses produce exactly one physical source family and identical selected geometry in every repeat.
- **SC-002**: Synthetic variants containing two genuinely separate walls produce at least two physical source families and remain ambiguous in 100% of repeats.
- **SC-003**: Corrected `bad-0102` is valid only after the radial two-wall, 5/5 curved-floor, normalized-profile and fixture-source proofs all pass; the original photometric failure remains visible in diagnostics.
- **SC-004**: Corrected `bad-0015` remains invalid with its mixed/occluded evidence preserved and all pose, correction, direction and PLC command fields null.
- **SC-005**: Five repeated runs of representative recovered and rejected cases produce identical status, family membership, representative geometry and diagnostic counts.
- **SC-006**: Reused-adapter warm processing remains at or below 2.5 seconds P95 per 5472×3648 image on the current reference server.
- **SC-007**: Focused unit and contract tests plus all root schemas pass, and prior-strategy compatibility tests show no unrequested behavior change.
- **SC-008**: The final report identifies observed versus physically separate validation data and makes no production accuracy or PLC authorization claim.

## Assumptions

- Corrected `bad-0015` and `bad-0102` task IDs and image hashes are immutable and the package interpretation remains `CODEX_PREFILL — NOT HUMAN TRUTH`.
- A physically separate new-part acceptance group is not yet available; implementation may be completed and regression-tested, but production accuracy cannot be claimed.
- Existing image coordinate, clockwise-angle and null-on-failure contracts remain authoritative.
- No global threshold relaxation is required; the defect spans physical source identity before the existing uniqueness gate and overly coarse fixture/photometric interpretation after a complete U contour is established.
