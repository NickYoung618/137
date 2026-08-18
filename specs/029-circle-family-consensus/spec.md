# Feature Specification: Circle-Family Consensus Stabilization

**Feature Branch**: `029-circle-family-consensus`

**Created**: 2026-08-18

**Status**: Draft

**Input**: Repair false physical-circle rejection caused by unstable representative selection inside one already-unique edge family, without weakening any quality or ambiguity gate.

## User Scenarios & Testing

### User Story 1 - Accept a normal circle from stable family consensus (Priority: P1)

As the inspection owner, I need a clearly visible physical outer circle to be measured consistently when several nearby image-edge samples describe the same boundary, so harmless pixel noise cannot change which member hypothesis represents an otherwise unique circle family.

**Why this priority**: Two visually normal part-023 frames contain sufficient circle evidence and pass when their own sparse circle is used to reassign final-ray candidates, but the current representative hypothesis causes a false final rejection.

**Independent Test**: Replay frozen frames 442 and 449 without changing their images or any existing circle thresholds. Each must retain exactly one eligible family and pass the unchanged final quality gates after consensus stabilizes.

**Acceptance Scenarios**:

1. **Given** one eligible circle family containing several nearby member hypotheses, **When** their ray assignments differ on adjacent edge layers, **Then** the family is consolidated from all bounded member evidence before authoritative point selection.
2. **Given** the same image and configuration are evaluated repeatedly, **When** corrective consensus is needed, **Then** the selected family, assignments, fitted circle and diagnostics are identical.
3. **Given** frozen frames 442 and 449, **When** the stabilized family is evaluated, **Then** each passes the existing residual, coverage, center, radius and inlier gates without threshold relaxation.

---

### User Story 2 - Preserve ambiguity and safe failure (Priority: P1)

As the safety owner, I need genuinely different physical circle families and unstable family evidence to remain invalid, so consensus cannot average incompatible circles into a plausible result.

**Why this priority**: A recovery that merely smooths or averages every hypothesis could hide real ambiguity.

**Independent Test**: Synthetic cases cover two distinct qualified families, non-convergent assignments, missing rays and nonfinite candidates. They must fail explicitly with null downstream pose and PLC fields.

**Acceptance Scenarios**:

1. **Given** two geometrically distinct qualified circle families, **When** selection runs, **Then** the result remains ambiguous and neither family is averaged with the other.
2. **Given** one grouped family whose bounded reassignment cannot stabilize, **When** the iteration limit is reached, **Then** the family is rejected with an explicit consensus failure.
3. **Given** missing, nonfinite or insufficient evidence, **When** consensus runs, **Then** no circle is fabricated.

---

### User Story 3 - Preserve frozen compatibility and diagnostics (Priority: P2)

As the algorithm maintainer, I need the new decision to be versioned and auditable while old configurations remain reproducible.

**Why this priority**: The committed 026 and 028 evidence must remain reproducible, and Mac replay must identify the exact strategy under test.

**Independent Test**: Run focused unit/contract tests, the six-image 026 compatibility set, and the frozen 140-image observed cohort with both legacy and new strategy configurations.

**Acceptance Scenarios**:

1. **Given** an existing configuration using the version-1 strategy, **When** it runs under the new code, **Then** its selection logic and outputs remain unchanged.
2. **Given** the version-2 strategy, **When** a family is selected or rejected, **Then** diagnostics record consensus inputs, iteration count, convergence, assignment changes and final family quality.
3. **Given** any invalid or ambiguous result, **When** the root result is built, **Then** angle, correction, direction, mechanical correction and PLC command remain null and PLC authority remains false.

### Edge Cases

- A family contains only one distinct hypothesis or all members have identical assignments.
- Coordinate-wise family consensus is finite but the first reassignment changes many rays.
- Assignments oscillate between nearby edge layers instead of stabilizing.
- Consensus reduces support or angular coverage below the existing family gates.
- Two distinct families are close in center/radius but do not share sufficient ray assignments.
- The sparse proposal succeeds while the independent final family has zero or multiple qualified families.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST retain the existing bounded hypothesis generation and inter-family uniqueness decision.
- **FR-002**: Under the new strategy, a grouped family whose preliminary residual already satisfies the unchanged authoritative residual gate MUST preserve the version-1 representative and observed assignments; a family exceeding that gate MUST form a corrective representative from all bounded member hypotheses.
- **FR-003**: Corrective family consensus MUST repeatedly assign at most one observed candidate per ray, refit from those observed points, and stop only on identical assignments or a fixed bounded iteration limit.
- **FR-004**: The system MUST reject nonfinite, insufficient-support or non-convergent consensus and MUST NOT fabricate or interpolate circle points.
- **FR-005**: Consensus MUST occur only within one already-grouped family and MUST NOT combine distinct qualified families or use sparse-stage family identity as final-stage authority.
- **FR-006**: Candidate and family decisions MUST be invariant to filename, sample identity, target/groove angle, manual truth, dictionary order and candidate enumeration order.
- **FR-007**: Existing final inlier, residual, angular coverage, center-shift and radius gates MUST remain unchanged.
- **FR-008**: Existing version-1 configurations MUST retain their previous behavior; new behavior MUST use an explicit version-2 strategy identifier.
- **FR-009**: Diagnostics MUST record whether correction was applied, the unchanged trigger gate, original residual, member-hypothesis count, consensus iteration count, convergence status, assignment-change counts, final support/coverage/residual and explicit failure checks.
- **FR-010**: Multiple qualified families MUST remain ambiguous; zero qualified families MUST fail explicitly; neither case may release pose or guidance.
- **FR-011**: Invalid and ambiguous root results MUST retain null angle, correction, direction, mechanical correction and PLC command fields with non-authoritative PLC status.
- **FR-012**: Tests MUST cover representative-hypothesis bias, candidate-order invariance, rotation invariance, non-convergence, multiple families, missing/nonfinite evidence and version-1 compatibility.
- **FR-013**: The frozen 140-image set MUST remain observed development evidence only. Frames 442 and 449 MUST be replayed from their frozen hashes, while the 41 reviewed mixed/occluded groove cases MUST remain fail-closed.
- **FR-014**: Warm reused-adapter performance MUST remain at or below 2.5 seconds P95 per 5472×3648 image and image loading MUST remain once per estimate.
- **FR-015**: The work MUST NOT merge main, modify PLC/HMI, access sealed part-006, claim production accuracy, or authorize PLC use.

### Key Entities

- **Member Hypothesis**: One bounded circle proposal with its observed per-ray candidate assignments and preliminary quality.
- **Family Consensus**: The finite representative circle, observed assignments, convergence history and final preliminary quality formed only from members of one grouped family.
- **Consensus Diagnostic**: Versioned evidence describing member count, iterations, assignment changes, convergence and failures.
- **Observed Regression Cohort**: The frozen 140 image hashes grouped into seven physical parts, used only for development regression.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Frozen frames 442 and 449 each retain exactly one qualified final edge family and pass all unchanged physical-circle quality gates.
- **SC-002**: On each recovered frame, the final residual P95 is no greater than the existing configured threshold and no circle threshold differs from the 028 configuration.
- **SC-003**: All other 138 frozen cohort images preserve their prior terminal safety disposition; all 41 reviewed mixed/occluded groove cases remain invalid.
- **SC-004**: Five static repeats of frames 442 and 449 produce identical circle parameters, assignments, statuses and bounded diagnostic counts.
- **SC-005**: Synthetic multiple-family and non-convergent cases are rejected in 100% of repeats, with all pose and PLC command fields unavailable.
- **SC-006**: Version-1 focused tests and the six-image 026 compatibility replay remain equivalent to their frozen baseline.
- **SC-007**: Focused tests and every root JSON Schema pass, and the repository has no uncommitted changes after the final evidence commit.
- **SC-008**: Reused-adapter warm performance remains at or below 2.5 seconds P95 and each estimate loads its image exactly once.
- **SC-009**: The final report identifies the branch, commit, config hash, image hashes, per-stage counts and observed-development limitation, and does not claim production readiness or PLC authority.

## Assumptions

- Frames 442 and 449 are immutable and their archived result image hashes match the current server copies.
- The physical outer circle is visually normal; the observed defect is candidate assignment instability within one grouped edge family.
- Existing family grouping thresholds and final circle gates remain authoritative unless separate new evidence justifies a future specification.
- The Mac 700-image replay will use frozen code and configuration after server validation and remains diagnostic rather than unseen acceptance.
