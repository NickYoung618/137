# Feature Specification: Position-Independent Radial U-Contour Ownership

**Feature Branch**: `codex/033-radial-u-contour-ownership`

**Created**: 2026-08-20

**Status**: Draft

**Input**: Diagnose and fix complete visible grooves that are rejected near fixture evidence by proving the position-independent physical shape of the housing groove itself: two radial sidewalls joined by a complete U-shaped floor on the detected outer circle, while every genuinely fixture-mixed or occluded case remains fail-closed at any circular position.

## User Scenarios & Testing

### User Story 1 - Prove the groove by its own physical shape (Priority: P1)

As the inspection owner, I need a complete groove at any circular position to remain usable when its refined radial walls, outer-circle endpoints, joined floor and normalized source shape prove a physical housing U-contour rather than a fixture edge.

**Why this priority**: Fifteen reviewed complete-visible results reach accepted physical geometry, but coarse fixture overlap remains authoritative. A location-specific gap rule would fix only this batch and fail when the groove rotates elsewhere.

**Independent Test**: Rotate the same synthetic U-contour around the full circle and vary nearby fixture sectors and lighting. The ownership result must depend only on the contour's measured radial geometry and source shape.

**Acceptance Scenarios**:

1. **Given** one complete refined U-shaped opening whose two observed walls follow the physically possible radial envelope from their outer-circle endpoints to a joined floor, **When** it appears at any image angle, **Then** a versioned contour proof may establish housing ownership.
2. **Given** the same geometry with one wall or floor removed, **When** ownership is checked, **Then** fixture ownership remains unresolved and the image stays invalid.
3. **Given** a smaller nested response and a complete response from the same visible region, **When** only the complete response proves the radial U-contour, **Then** the smaller failed response cannot prevent the complete response from being selected by the existing ambiguity resolver.

---

### User Story 2 - Separate lighting strength from source shape (Priority: P1)

As the inspection owner, I need two physically complete walls to remain same-source when only their raw brightness or gradient strength differs and their normalized shape, endpoints and coverage agree.

**Why this priority**: All fifteen complete-visible cases pass the locked normalized profile and radial-coverage checks; they are rejected only by raw photometric imbalance plus the unresolved fixture-overlap proof.

**Independent Test**: Vary brightness and gradient magnitude independently on two synthetic walls while preserving normalized profiles and physical ownership. Verified cases pass without changing any existing threshold; corrupted or fixture-mixed variants remain rejected.

**Acceptance Scenarios**:

1. **Given** verified radial U-contour ownership and two complete walls whose normalized profile, coverage and endpoint structure pass existing checks, **When** only raw contrast or gradient balance fails, **Then** a versioned source decision may accept the physical source without changing original measurements or thresholds.
2. **Given** normalized-shape, coverage, endpoint, wall, floor or ownership evidence fails, **When** raw brightness differs, **Then** the result remains invalid.
3. **Given** any non-photometric source failure that was not already safely adjudicated by the unchanged version-4 complete-U or visible-boundary route, **When** the new radial-U route is evaluated, **Then** that failure remains authoritative.

---

### User Story 3 - Preserve safe rejection and auditability (Priority: P1)

As the safety owner, I need fixture-mixed, occluded, ambiguous and incomplete grooves to remain rejected, with a clear record of why ownership was accepted or denied.

**Why this priority**: Sixty-seven reviewed results are genuinely fixture-mixed or occluded. Recovering complete openings must not release them or weaken null-on-failure behavior.

**Independent Test**: Replay synthetic ownership boundaries and the immutable observed diagnostic cohort. Every proven occluded comparison remains invalid, prior configurations stay unchanged, and every decision is deterministic and versioned.

**Acceptance Scenarios**:

1. **Given** both refined endpoints lie on or behind the same fixture body, or a fixture hides or replaces a wall, **When** ownership is checked, **Then** the image remains invalid with an explicit reason and all guidance fields null.
2. **Given** two genuinely different qualified openings, **When** the existing ambiguity resolver runs, **Then** they remain ambiguous; ownership proof cannot choose by score, position or candidate order.
3. **Given** a prior or disabled configuration, **When** the same image is processed, **Then** previous behavior and accepted contract fields remain unchanged.

### Edge Cases

- The complete groove is rotated to an angle not present in the observed diagnostic set.
- Both apparent walls come from one curved or tangential fixture edge.
- One wall is radial but the opposite wall is tangential or truncated.
- Fixture sectors are missing, non-unique, nonfinite or reordered.
- Two candidates share one partial wall but only one has a complete floor and opposite wall.
- Raw contrast and normalized profile shape both fail.
- The lower large fixture is nearby but does not cover the housing boundary.
- The upper small fixture hides only one wall or endpoint.
- More than one physical groove survives all checks.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST keep coarse candidate-fixture overlap separate from refined physical U-contour ownership; coarse overlap alone MUST NOT prove either acceptance or rejection.
- **FR-002**: Housing ownership MAY be verified only from two finite observed groove walls and outer-circle endpoints, a complete observed floor, and two wall directions that remain within the physically possible radial envelope defined by the measured opening width and the existing unchanged intersection tolerance.
- **FR-003**: Ownership verification MUST be rotation-independent and use refined observed geometry; it MUST NOT use fixture gap location, candidate score, filename, sample identity, capture order, directory class, target angle, fixed-angle lists, manual labels or observed-set membership.
- **FR-004**: The ownership decision MUST be deterministic under candidate, endpoint and fixture-sector ordering and MUST fail closed for missing, nonfinite, non-unique or tangential-wall evidence.
- **FR-005**: A smaller nested candidate that fails physical evidence MUST remain recorded but MUST NOT block one different candidate that independently passes the existing full refinement, source and uniqueness chain.
- **FR-006**: The source decision MAY adjudicate raw contrast or gradient imbalance only when radial U-contour ownership is verified and all existing normalized-profile, radial-coverage and endpoint-structure checks pass.
- **FR-007**: The source decision MUST NOT remove failures for missing walls, missing endpoints, incomplete floor, incompatible normalized profiles, incompatible radial coverage, endpoint inconsistency, mixed/occluded evidence, ambiguity, nonfinite values or any upstream failure.
- **FR-008**: Existing global ambiguity, recognition, refinement, polar-quality, fixture and source-consistency thresholds MUST remain unchanged.
- **FR-009**: Two genuinely distinct qualified physical openings MUST remain separate and trigger existing ambiguity behavior.
- **FR-010**: The new ownership and source behavior MUST be explicit, bounded, versioned and disabled for prior configurations.
- **FR-011**: Diagnostics MUST record coarse overlaps, measured opening width, both wall-to-radius alignment values, the derived position-independent radial envelope, wall/floor/profile checks, original source failures, effective failures, decision basis and failed checks without private paths or manual truth.
- **FR-012**: Every rejected result MUST keep angle, correction, direction, mechanical command and PLC command fields null and PLC execution non-authoritative.
- **FR-013**: Work per image MUST be bounded and MUST NOT add another image decode, full-circle search, polar resampling or repeated full refinement chain.
- **FR-014**: Tests MUST cover the same valid U-contour rotated around the circle, tangential fixture edges, one-wall loss, floor loss, normalized-shape corruption, coverage loss, endpoint inconsistency, nonfinite evidence, input ordering, nested failed candidates, true ambiguity, prior compatibility, static repeatability and warm performance.
- **FR-015**: The reviewed A2-700 images are observed diagnostic data only; they MAY demonstrate regression behavior but MUST NOT be used as unseen acceptance or production-accuracy evidence.
- **FR-016**: A physically separate new-part group MUST pass before any accuracy-improvement, production-readiness or PLC-authorization claim.
- **FR-017**: The work MUST NOT read sealed part-006, modify PLC/HMI or merge main.
- **FR-018**: Version 5 MUST preserve every decision already authorized by the unchanged version-4 complete-U or visible-boundary proof; the new radial-U route is additive and MAY remove only raw contrast/gradient failures after its stricter proof passes.
- **FR-019**: Portable profile v8 MUST explicitly disable the superseded development-only local-second-wall diagnostic while preserving it in prior profiles; this diagnostic MUST NOT affect pose decisions, safety nulls or PLC state.

### Key Entities

- **Coarse Fixture Overlap**: The bounded angular intersection between one coarse candidate and image-derived fixture sectors; diagnostic only and never physical ownership by itself.
- **Refined Opening Boundary**: Two observed sidewalls, finite outer-circle endpoints and an observed curved floor after physical refinement.
- **Radial U-Contour Ownership Proof**: A versioned, rotation-independent decision that both refined walls and their joined floor form a physically possible housing opening rather than a tangential fixture edge.
- **Effective Source Decision**: An independent source result that preserves original photometric failures and can accept only after ownership and all locked shape checks pass.
- **Observed Diagnostic Cohort**: Immutable image hashes, runtime results and visual review used for diagnosis and regression only.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A verified synthetic U-contour produces the same ownership decision at every tested circular rotation and under every candidate, endpoint and fixture-sector ordering.
- **SC-002**: Removing or corrupting each required fixture, wall, endpoint, floor, profile or coverage proof causes 100% of cases to remain invalid with an explicit reason.
- **SC-003**: Complete verified openings that differ only in raw lighting magnitude pass source proof in 100% of deterministic repeats without changing existing thresholds.
- **SC-004**: Same-fixture, mixed, occluded and genuinely ambiguous synthetic cases remain fail-closed with complete safety nulls.
- **SC-005**: The 15 reviewed complete-visible diagnostic cases proceed successfully, while all 67 reviewed fixture-mixed or occluded cases remain invalid with complete safety nulls.
- **SC-006**: No previously valid result in the observed A2-700 replay becomes invalid, and no reviewed mixed/occluded result becomes valid.
- **SC-007**: Five repeated runs of representative accepted, ambiguous and occluded cases have identical non-timing diagnostics and outputs.
- **SC-008**: Reused-adapter warm P95 remains at or below 2.5 seconds per 5472×3648 image, with one image load and no repeated full analysis pass.
- **SC-009**: Focused tests, the full available test suite, all root schemas and strict configuration validation pass.
- **SC-010**: Reports clearly separate observed diagnostic regression from physically separate acceptance and make no production or PLC claim before new-part validation.

## Assumptions

- The fifteen reviewed complete-visible cases share one terminal root cause: complete physical evidence is blocked because coarse fixture overlap outranks a position-independent radial U-contour ownership proof that is not yet represented.
- Nested candidates in fourteen cases are diagnostic context, not the terminal blocker; the existing resolver can select the complete candidate once its source is verified.
- The sixty-seven reviewed mixed/occluded cases are safety regression controls, not examples to be released.
- Existing fixture sectors, refined walls, endpoints, floor and source profiles can be reused without decoding or sampling the image again.
- Prior configuration versions remain reproducible and the new behavior is enabled only by a new reviewed portable profile.
