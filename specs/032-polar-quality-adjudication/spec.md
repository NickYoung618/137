# Feature Specification: Physical-Groove Polar Quality Adjudication

**Feature Branch**: `codex/032-polar-quality-adjudication`

**Created**: 2026-08-20

**Status**: Draft

**Input**: Prevent a complete, uniquely refined physical groove from being rejected solely because the legacy whole-ring polar registration score is slightly below its unchanged threshold, while preserving the original score, all existing geometry/source gates, and fail-closed behavior for fixture-mixed or occluded grooves.

## User Scenarios & Testing

### User Story 1 - Release a complete physical groove after independent proof (Priority: P1)

As the inspection owner, I need a complete visible groove to remain usable when its physical outer circle, two sidewalls, endpoints, curved floor and source identity are independently established, even if unrelated whole-ring texture lowers the legacy polar registration score.

**Why this priority**: In one observed 20-frame sequence, the same complete groove is far from the stationary fixtures and every physical groove gate passes, but the whole-ring polar score remains between 2.845 and 2.928 against the unchanged threshold of 3.0. Rejecting those frames loses otherwise complete image-derived pose evidence.

**Independent Test**: Supply synthetic and representative diagnostic inputs in which the polar score alone fails while every required physical-groove proof passes. The result may release image pose without changing the score or threshold, and the decision records every independent proof used.

**Acceptance Scenarios**:

1. **Given** one unique physical outer circle and exactly one complete visible groove with two distinct radial walls, finite outer endpoints, an independently complete curved floor and accepted source consistency, **When** only the whole-ring polar score fails, **Then** a versioned adjudication may release the image-frame pose while preserving the original failed score and threshold.
2. **Given** the same physical evidence under reordered diagnostics or repeated execution, **When** adjudication is evaluated, **Then** the decision and released pose are identical.

---

### User Story 2 - Keep uncertain, mixed and occluded grooves rejected (Priority: P1)

As the safety owner, I need the polar exception to remain unavailable whenever the groove source is incomplete, ambiguous, fixture-mixed or occluded, so a low global quality score cannot be bypassed by weak local evidence.

**Why this priority**: The observed cohort contains 174 runtime mixed/occluded results and known fixture-contaminated cases. Their null-on-failure behavior must not regress.

**Independent Test**: Remove or corrupt each required physical proof one at a time, provide multiple candidates, nonfinite values and mixed/occluded source evidence, and verify that all cases remain invalid with null guidance and non-authoritative PLC output.

**Acceptance Scenarios**:

1. **Given** missing, ambiguous, nonfinite or inconsistent wall, endpoint, floor, source or fixture evidence, **When** the polar score fails, **Then** adjudication is denied with an explicit reason and the result remains invalid.
2. **Given** a wall mixed with or hidden by a stationary fixture, **When** the polar score fails or passes, **Then** this feature never converts the result to valid.
3. **Given** any non-polar quality failure, **When** adjudication is evaluated, **Then** the failure remains authoritative.

---

### User Story 3 - Preserve compatibility and auditability (Priority: P2)

As the algorithm maintainer, I need the new decision to be explicit, bounded, versioned and disabled for prior configurations so old results remain reproducible and every release can be audited without private labels.

**Why this priority**: The 700-frame set is already observed diagnostic data. An opaque or globally enabled exception would hide regressions and could turn reviewed data into a tuning rule.

**Independent Test**: Run prior and new configurations over the same deterministic fixtures, validate diagnostics, and verify that the prior path is unchanged while the new path reports original and effective quality separately.

**Acceptance Scenarios**:

1. **Given** a prior configuration or a disabled adjudication, **When** the polar score is below threshold, **Then** the legacy rejection behavior is unchanged.
2. **Given** enabled adjudication, **When** it accepts or rejects, **Then** diagnostics record the original score, unchanged threshold, original failure, physical proofs, decision, effective status and all failed checks.

### Edge Cases

- The polar score equals the threshold exactly.
- The polar score or threshold is missing, nonfinite or malformed.
- The polar score fails together with scale, ambiguity, recognition, refinement, source or fixture checks.
- Two groove candidates independently appear complete.
- Two wall responses actually belong to one wall family, or two distinct wall families remain comparable.
- The curved floor is incomplete even though two lines are present.
- A complete groove lies near a fixture but verified image evidence separates their sources.
- The runtime source classification conflicts with lower-level physical evidence.
- Diagnostics arrive in a different order or contain additional open diagnostic fields.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST preserve the legacy polar score, its unchanged threshold and the original `polar_score` failure before any adjudication.
- **FR-002**: Adjudication MUST be explicit, versioned, bounded and disabled unless a compatible configuration enables it.
- **FR-003**: Adjudication MAY release image pose only when `polar_score` is the sole remaining final-quality failure.
- **FR-004**: Adjudication MUST require one accepted physical outer circle with exactly one qualified outer-circle edge family.
- **FR-005**: Adjudication MUST require exactly one accepted real-groove candidate and an accepted refinement containing two distinct observed radial sidewalls with finite outer-circle endpoints.
- **FR-006**: Adjudication MUST require an independently accepted complete curved floor and MUST NOT infer a floor from the two wall lines.
- **FR-007**: Adjudication MUST require accepted effective source consistency and, whenever fixture proximity or overlap is present, verified fixture-source exclusion based on image-derived geometry.
- **FR-008**: Any ambiguity, mixed/occluded classification, missing proof, insufficient evidence, nonfinite value or non-polar quality failure MUST deny adjudication and preserve the invalid result.
- **FR-009**: Filename, sample identity, capture index, fixed angle, target angle, directory class, manual review and observed-set membership MUST NOT participate in runtime adjudication.
- **FR-010**: The new decision MUST NOT lower or replace the existing polar, recognition, refinement, source-consistency, ambiguity, fixture, scale or outer-circle thresholds.
- **FR-011**: Released pose MUST come only from the accepted refined physical groove; the legacy polar rotation MUST NOT replace, blend with or bias the groove pose.
- **FR-012**: Diagnostics MUST record original and effective quality states, every required physical proof, decision margins, decision reason, strategy version and whether pose release was allowed, without private paths or manual labels.
- **FR-013**: Prior configurations and disabled adjudication MUST retain their existing behavior and accepted contract fields.
- **FR-014**: Invalid or denied results MUST keep angle, correction, direction, mechanical command and PLC command fields null, with PLC non-authoritative.
- **FR-015**: Work per image MUST be bounded and MUST NOT add another image decode, full-frame polar resampling, physical-circle search or groove-refinement pass.
- **FR-016**: Tests MUST cover sole-polar failure, threshold equality, every missing proof, multiple candidates, mixed/occluded evidence, nonfinite input, diagnostic ordering, prior compatibility, null safety, static repeatability and warm performance.
- **FR-017**: The observed 20-frame sequence, 24 recovered-valid frames and full A2-700 replay MUST remain diagnostic evidence and MUST NOT be used as unseen acceptance or production-accuracy evidence.
- **FR-018**: A physically separate new-part group MUST pass before any accuracy-improvement, production-readiness or PLC-authorization claim.
- **FR-019**: The work MUST NOT read sealed part-006, modify PLC/HMI or merge main.

### Key Entities

- **Original Polar Quality Evidence**: Immutable score, threshold, failed checks and legacy effective status before adjudication.
- **Physical Groove Proof**: The bounded set of unique outer-circle, two-wall, endpoint, curved-floor, source-consistency and fixture-exclusion facts required for a decision.
- **Polar Quality Adjudication**: A versioned accept-or-deny decision that can remove only the sole `polar_score` terminal failure without altering its evidence.
- **Effective Quality State**: The post-adjudication state used to decide whether image pose may proceed; it remains separate from original quality evidence.
- **Observed Diagnostic Case**: Immutable task ID, image hash, result and visual evidence used for regression but not acceptance truth.

## Success Criteria

### Measurable Outcomes

- **SC-001**: In synthetic sole-polar-failure cases with every physical proof present, 100% of deterministic repeats release the same image pose while preserving the failed original score and threshold.
- **SC-002**: Removing each required proof one at a time causes 100% of cases to remain invalid with an explicit denial reason.
- **SC-003**: Every mixed/occluded, ambiguous, multiple-candidate, nonfinite and non-polar-failure test remains fail-closed with complete safety nulls.
- **SC-004**: Prior and disabled configurations reproduce their pre-feature decisions and diagnostics in all compatibility fixtures.
- **SC-005**: The observed 20-frame complete-visible sequence proceeds past the sole polar failure only through the versioned physical-proof decision; no threshold changes and no runtime review labels are present.
- **SC-006**: The 24 previously recovered valid observed frames remain valid and the 174 runtime mixed/occluded observed frames remain invalid in the frozen diagnostic replay.
- **SC-007**: Five repeated runs of representative released and denied cases have identical non-timing decisions, proof fields and pose/null outputs.
- **SC-008**: Reused-adapter warm P95 remains at or below 2.5 seconds per 5472×3648 frame, and diagnostics prove no repeated image load or analysis pass was added.
- **SC-009**: Focused tests, full available tests, all root schemas and strict configuration validation pass.
- **SC-010**: Reports distinguish CODEX pre-review, human-confirmed truth, observed regression and physically separate acceptance, and make no production or PLC claim before new-part validation.

## Assumptions

- In single-real-groove mode, the authoritative image pose is derived from refined groove geometry rather than legacy polar rotation.
- Existing outer-circle, groove-refinement, curved-floor, source-consistency and fixture-source diagnostics are available before final quality adjudication.
- The 20 observed frames are consecutive captures of one visible groove condition and therefore count as one observed root-cause sequence, not 20 independent physical parts.
- Human confirmation and physically separate new-part acceptance remain external gates; CODEX pre-review cannot replace either.
