# Feature Specification: Main Housing Registration for A2 Short Lines

**Feature Branch**: `007-main-housing-registration`  
**Created**: 2026-08-14  
**Status**: In progress

## Evidence and scope

The external A2 LabelMe anchor identifies true feature 19 and 30 edges on
`representative.bmp` (5472x3648). Its annotation SHA-256 is
`a175dd831fbc94913f9b9c69a04f81b0be7b58c0355118551c4447b967b3271c` and
its image SHA-256 is
`72912fb27a7127c7db3e425d896c9337d6a227a673b8396dc6026dab40c4b5b3`.
The previous core transform selects or biases toward a neighboring right-hand
part on A2; therefore its predicted 19/30 lines are diagnostic evidence only
and MUST NOT seed the v2 candidate search.

This increment only changes the 137 A-end-face candidate and tooling paths. It
does not modify `algorithms/end_face/core.py`, legacy measurements,
`coreValid`, localization, measurement completeness, or the `caozitai`
repository. Raw A2 images and result JSONL remain external to Git.

## User scenarios and testing

### US1 — Select the main housing instance (Priority: P1)

An engineer runs the v2 candidate on an image containing the main housing and
neighboring circular parts. The system enumerates plausible circular housing
instances and chooses the one whose scale, circular support and reference
appearance best match the externally labeled main housing.

**Independent test**: a synthetic multi-instance image places a convincing
neighbor where the legacy transform points; v2 must select the independently
registered main instance or fail closed.

**Acceptance scenarios**:

1. **Given** a valid external 19/30 LabelMe anchor and a target with multiple circular parts, **when** v2 registration runs, **then** its chosen center is derived without reading legacy 19/30 target geometry.
2. **Given** no instance passes the explicit support and ambiguity gates, **when** v2 runs, **then** both candidates remain invalid with traceable registration failure reasons.

### US2 — Register center, scale, and angle (Priority: P1)

The selected main housing is aligned to the external reference using a robust
circle fit for center and scale plus an independent angular signature. The
registered external 19/30 lines then define local edge-search regions.

**Independent test**: a transformed synthetic target with a distractor must
recover center, scale and angle within configured tolerances, and projected
anchor endpoints must lie near the known transformed truth.

**Acceptance scenarios**:

1. **Given** sufficient circular support and an unambiguous angular match, **when** the reference is transformed, **then** the output records selected instance, fit support, residual, scale, rotation and registration score.
2. **Given** ambiguous rotation or excessive scale change, **when** registration is gated, **then** no candidate is declared valid.

### US3 — Preserve independent candidate semantics (Priority: P1)

An engineer compares baseline core and v2 candidate results per image. Legacy
outputs remain unchanged while each short line reports its own
`candidateValid` and `both_valid`/`recovered`/`regressed`/`both_invalid`
transition.

**Independent test**: snapshot legacy measurements and feature quality before
candidate evaluation, then assert equality afterwards while validating v2
schema and transitions.

### US4 — Run external Mac A2 evaluation (Priority: P2)

An engineer freezes the v2 config and anchor hashes, then runs the comparison
CLI against an external manifest for the first 25 A2 images. The generated
JSONL and summary stay outside Git.

**Independent test**: command construction and manifest handling are covered
on server-accessible synthetic assets; the real 25-frame claim is produced
only by the Mac run.

### Edge cases

- The target contains no complete main housing circle, two similarly scored
  instances, severe cropping, or out-of-frame projected endpoints.
- The anchor image is itself presented as target; registration must be stable
  without using legacy target measurements.
- The external annotation or image differs from the pinned SHA-256 values.
- Circle support is dominated by a neighboring component or rotation has a
  repeated/flat correlation peak.

## Functional requirements

- **FR-001**: Add a versioned v2 candidate whose registration starts from the external A2 reference image and annotation, not legacy target measurement geometry.
- **FR-002**: Enumerate and score multiple main-housing instance hypotheses before selecting one.
- **FR-003**: Estimate center and scale from robust circular edge support and estimate angle from reference-to-target appearance.
- **FR-004**: Apply explicit gates for support, circular residual, scale range, instance ambiguity, rotation confidence and projected in-frame coverage.
- **FR-005**: Project external 19/30 annotations through the accepted transform and perform only local boundary/template refinement around those projected lines.
- **FR-006**: Preserve independent `candidateValid` and transition semantics; v2 MUST NOT write candidate values into legacy measurements or `coreValid`.
- **FR-007**: Preserve the existing v1 candidate as an explicitly selectable compatibility mode.
- **FR-008**: Record candidate/config/reference hashes plus instance and registration diagnostics in single and batch comparison output.
- **FR-009**: Fail closed when v2 has no external LabelMe reference; no old prediction may be substituted as pseudo-label geometry.
- **FR-010**: Supply an external-manifest command for the Mac 25-frame run without copying images or JSONL into Git.
- **FR-011**: Keep `algorithms/end_face/core.py` byte-identical at SHA-256 `f408631e03563ac80f392ea7558b786c2e2bef61670d1f206486f883b9ff8fbc`.

## Key entities

- **Housing hypothesis**: proposed center/radius with edge support, coverage,
  residual and instance score.
- **Registration result**: selected hypothesis, scale, rotation, confidence,
  ambiguity margin, gates and failure reason.
- **Short-line candidate**: projected/refined 19 or 30 geometry with independent
  checks, `candidateValid`, transition and provenance.

## Success criteria

- **SC-001**: The pinned external representative image passes a self-anchor registration test and projects both labels within 2 px before local refinement.
- **SC-002**: Synthetic multi-instance tests select the true main housing while a legacy-like neighbor distractor is present.
- **SC-003**: Missing/ambiguous/low-support registration cases fail closed without changing any legacy field.
- **SC-004**: Full tests, result schemas, immutable-core SHA audit and raw/large-file Git audit pass.
- **SC-005**: Documentation reports the representative-image result only as an anchor result and provides, but does not pre-claim, the external Mac 25-frame comparison.

## Assumptions

- The main housing is the dominant approximately circular instance and retains
  enough visible boundary and asymmetric annular appearance across A2 frames.
- The supplied annotation/image pair is the only accepted A2 geometric anchor
  for this increment.
- Real A2 25-frame performance must be measured where those external images
  are available; server synthetic evidence cannot substitute for it.
