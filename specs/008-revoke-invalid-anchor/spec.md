# Feature Specification: Revoke Invalid A2 Short-Line Anchor

**Feature Branch**: `008-revoke-invalid-anchor`
**Created**: 2026-08-14
**Status**: Implemented; real A2 19/30 acceptance blocked pending corrected truth

## Context and scope

Radial-gradient review shows that the previously supplied A2 19/30 annotation
does not snap to the actual stepped boundaries. Its annotation SHA-256
`a175dd831fbc94913f9b9c69a04f81b0be7b58c0355118551c4447b967b3271c`
is therefore revoked. It is a denylisted input, not truth, tuning data, or
acceptance evidence. Earlier single-image candidate outcomes derived from it
are void and must not be repeated as recovery claims.

This increment quarantines the revoked input, separates main-housing
registration from short-line coordinates, and continues only work that can be
validated without A2 19/30 truth. Real short-line acceptance remains blocked
until a corrected manual annotation is supplied. The immutable desktop core
and every legacy result semantic remain outside this change.

## User scenarios and testing

### US1 — Reject the revoked annotation everywhere (Priority: P1)

An engineer accidentally supplies the revoked annotation to the inspector,
batch evaluator, comparison tool, or annotation inspector. The operation
fails before template construction or candidate evaluation and explains that
the reference was revoked.

**Independent test**: a controlled file whose computed fingerprint matches the
revocation entry is rejected through the shared loader; no candidate result is
produced.

**Acceptance scenarios**:

1. **Given** the revoked fingerprint, **when** any candidate reference loader is called, **then** it fails closed with a stable revocation error.
2. **Given** a different, structurally valid synthetic reference, **when** it is loaded, **then** normal validation continues.

### US2 — Register the main housing without 19/30 coordinates (Priority: P1)

An engineer develops center, scale, and angle registration using image
structure alone. Main-housing reference-instance selection does not read
short-line labels or endpoints.

**Independent test**: synthetic images with multiple circular instances,
translation, scale, rotation, ambiguity, and insufficient support exercise the
registration using no annotation object.

**Acceptance scenarios**:

1. **Given** a dominant supported main housing and smaller neighbors, **when** registration runs, **then** it selects the dominant instance and estimates the known transform.
2. **Given** two non-dominant or ambiguous reference instances, **when** the reference model is built, **then** it fails closed without accepting either as truth.

### US3 — Diagnose registration independently of measurement truth (Priority: P1)

An engineer runs a registration-only command over external images. The command
emits center/scale/angle hypotheses and gate results but no short-line
`candidateValid`, measurement, or recovery claim.

**Independent test**: a synthetic manifest produces strict JSONL and a summary
whose records contain only registration diagnostics and input provenance.

### US4 — Resume real 19/30 evaluation only with corrected truth (Priority: P2)

The Mac comparison command accepts a future corrected LabelMe file. Until that
file passes structural checks and is not revoked, documentation labels the
real short-line acceptance step as blocked.

**Independent test**: command documentation uses a corrected-reference
placeholder and never names the revoked file as runnable truth.

## Edge cases

- The revoked JSON is renamed or moved; fingerprint rejection still applies.
- The revoked JSON is embedded in another command path; all callers share the
  same loader and fail consistently.
- A reference image contains a large incomplete/cropped neighbor or two
  similarly sized complete circles.
- Registration succeeds but no corrected 19/30 annotation exists; registration
  diagnostics may be emitted, while short-line evaluation remains blocked.

## Functional requirements

- **FR-001**: The system MUST deny the revoked annotation fingerprint before it can act as a template, truth source, tuning input, or acceptance input.
- **FR-002**: Revocation MUST be path-independent and shared by single-image, batch, compare, and annotation-inspection entry points.
- **FR-003**: Main-housing reference selection MUST NOT consume 19/30 labels, endpoints, or any other measurement annotation.
- **FR-004**: Reference selection MUST require explicit circular support and dominance gates, and fail when those gates do not pass.
- **FR-005**: Target registration MUST preserve existing support, residual, scale, rotation-confidence, and ambiguity failure protection.
- **FR-006**: A registration-only diagnostic workflow MUST emit strict, image-free JSON/JSONL and aggregate counts without candidate recovery semantics.
- **FR-007**: Synthetic tests MUST cover reference dominance, multiple targets, non-zero scale/angle, ambiguity, missing support, and legacy-output immutability.
- **FR-008**: Documentation and specifications MUST retract the revoked anchor as evidence and label real 19/30 acceptance blocked pending corrected truth.
- **FR-009**: A future corrected annotation MUST still pass strict LabelMe structure and image consistency checks before candidate use.
- **FR-010**: `algorithms/end_face/core.py` MUST remain byte-identical at SHA-256 `f408631e03563ac80f392ea7558b786c2e2bef61670d1f206486f883b9ff8fbc`.
- **FR-011**: Candidate work MUST NOT alter legacy measurements, `coreValid`, localization, or measurement completeness.
- **FR-012**: No raw image, private annotation, archive, or generated JSONL may enter Git.

## Key entities

- **Revoked reference fingerprint**: a path-independent identifier that is
  prohibited from candidate use.
- **Annotation-independent reference housing**: dominant supported circle used
  to establish the registration coordinate system without dimension labels.
- **Registration diagnostic record**: input provenance, hypotheses, accepted or
  failed transform, and checks, with no measurement-truth status.
- **Corrected short-line reference**: future manually verified 19/30 LabelMe
  input required to unblock real candidate acceptance.

## Success criteria

- **SC-001**: Every supported reference-loading entry point rejects the revoked fingerprint in automated tests.
- **SC-002**: Registration tests run with zero 19/30 annotation inputs and recover synthetic center within 5 px, scale within 0.04, and rotation within 1.5 degrees.
- **SC-003**: Registration-only batch diagnostics produce strict JSON for all synthetic records and never contain `candidateValid`, `transition`, or `recovered` fields.
- **SC-004**: Full unit tests, schemas, static checks, core SHA audit, and large/raw-file audit pass.
- **SC-005**: Repository documentation contains no runnable acceptance command using the revoked annotation and makes no real 19/30 improvement claim.

## Assumptions

- The dominant complete outer circle is sufficient to identify the reference
  main housing in supported capture layouts; ambiguous layouts fail closed.
- The representative image itself may be used later for registration-only
  diagnostics, but not for 19/30 truth until corrected annotation exists.
- The next corrected annotation will have a different fingerprint and will be
  manually verified against radial-gradient boundary diagnostics.
