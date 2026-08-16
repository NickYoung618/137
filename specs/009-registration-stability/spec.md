# Feature Specification: Registration Stability Statistics

**Feature Branch**: `009-registration-stability`

**Created**: 2026-08-14

**Status**: Implemented; external Mac multi-frame execution pending

**Input**: Continue annotation-independent development by making external Mac
batch registration results quantitatively reviewable across frames without
using withdrawn or unverified 19/30 truth.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review cross-frame registration stability (Priority: P1)

An algorithm engineer runs the existing registration-only batch workflow over
an external sample and receives compact distributions for housing center,
radius, scale, angle, confidence, ambiguity margin, edge coverage, and circle
residual. The engineer can distinguish a stable registration series from
large drift or mixed-instance behavior without opening every record.

**Why this priority**: A valid-count alone cannot show whether accepted frames
lock onto one physical instance consistently. Quantitative distributions are
the next safe evidence available while short-line truth is unavailable.

**Independent Test**: Run a synthetic multi-frame batch with known transforms
and verify every supported metric includes all registration-valid frames and
matches the known distribution.

**Acceptance Scenarios**:

1. **Given** multiple registration-valid frames, **When** the batch summary is produced, **Then** it contains deterministic finite distributions for every supported linear metric.
2. **Given** valid rotations that straddle the signed-angle boundary, **When** angle stability is summarized, **Then** the result uses circular statistics and reports them as a tight cluster rather than a near-full-turn spread.

---

### User Story 2 - Preserve failed and sparse runs safely (Priority: P1)

An engineer runs a batch in which some or all frames fail registration. The
summary keeps technical and registration counts and failure reasons, while
metrics with no observations report an explicit zero count and null values.

**Why this priority**: Sparse or failed runs are expected during instance
selection development and must remain strict JSON rather than producing NaN,
misleading zero-valued geometry, or a crash.

**Independent Test**: Run a batch containing registration-invalid synthetic
images and validate the summary against its contract with no non-finite values.

**Acceptance Scenarios**:

1. **Given** no registration-valid frame, **When** the summary is produced, **Then** every stability metric has count zero and null descriptive values.
2. **Given** a mix of valid and invalid frames, **When** the summary is produced, **Then** only valid transforms contribute to geometry statistics while every failure remains counted by reason.

---

### User Story 3 - Run the same review on Mac external data (Priority: P2)

An engineer uses one command on a validated external Manifest and obtains
image-free JSONL plus the versioned stability summary. Images and outputs stay
outside Git, and the summary makes no short-line recovery or measurement
claim.

**Why this priority**: The real capture series exists on Mac and must be
reviewable with exactly the same frozen implementation tested on the server.

**Independent Test**: A server synthetic Manifest exercises the documented
command and contract; the documentation states that only the external Mac run
can supply real A2 registration evidence.

**Acceptance Scenarios**:

1. **Given** a validated external Manifest, **When** the batch command completes, **Then** its summary identifies the Manifest, reference image, core source, config, and diagnostic stream by fingerprint.
2. **Given** no corrected 19/30 truth, **When** the engineer reviews the output, **Then** no candidate-validity, transition, measurement, or recovery field is present.

### Edge Cases

- A batch contains exactly one registration-valid frame; spread and MAD are
  defined as zero without implying multi-frame stability.
- Rotations occur near `-180°` and `+180°`; circular statistics must remain
  continuous across the wrap boundary.
- Images have different dimensions; normalized center and radius values are
  computed per frame before aggregation.
- A selected hypothesis is absent or inconsistent with `selectedIndex`; that
  record remains registration-valid for existing semantics but unavailable
  hypothesis metrics are excluded by their own counts.
- Any input metric is null or non-finite; it is excluded rather than serialized
  as NaN or replaced with a fabricated value.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The batch summary MUST include linear distributions for target center x/y in pixels and normalized coordinates, target radius in pixels and normalized form, scale, rotation confidence and margin, instance-selection margin, edge coverage, and circular residual ratio.
- **FR-002**: Every linear distribution MUST report observation count, minimum, maximum, mean, median, fifth percentile, ninety-fifth percentile, and median absolute deviation using only finite observations.
- **FR-003**: Rotation stability MUST use circular statistics and report observation count, circular mean angle, resultant length, circular standard deviation, maximum absolute angular deviation, and median absolute angular deviation.
- **FR-004**: Geometry and confidence statistics MUST include only records whose technical execution succeeded and whose registration is valid.
- **FR-005**: Missing observations MUST produce count zero and null descriptive values; outputs MUST remain strict finite JSON.
- **FR-006**: The summary contract MUST be versioned and validated for successful, mixed, all-invalid, single-frame, and angle-wrap cases.
- **FR-007**: Summary provenance MUST retain dataset, Manifest, reference-image, immutable-core, candidate-config, and diagnostics-stream fingerprints.
- **FR-008**: Stability output MUST NOT contain or infer measurements, `coreValid`, localization, completeness, `candidateValid`, transition, or recovery status.
- **FR-009**: Existing per-frame registration gates and values MUST remain unchanged; stability statistics MUST NOT feed back into acceptance.
- **FR-010**: The withdrawn A2 annotation fingerprint MUST remain rejected and MUST NOT participate in statistics, tuning, or evidence.
- **FR-011**: `algorithms/end_face/core.py` and all legacy result semantics MUST remain unchanged.
- **FR-012**: Raw images, private annotations, archives, generated JSONL, and generated summaries MUST remain outside Git.

### Key Entities

- **Linear stability distribution**: finite observation count and robust/common
  descriptive values for one registration quantity.
- **Circular rotation distribution**: wrap-safe direction, concentration, and
  angular-deviation values for accepted rotations.
- **Registration stability summary**: versioned batch result combining
  provenance, validity/failure counts, and diagnostic-only distributions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a synthetic batch, every complete linear metric reports an observation count equal to the number of registration-valid frames and values matching the known inputs within `1e-9`.
- **SC-002**: Synthetic rotations at `+179°` and `-179°` produce a circular mean within `1°` of the wrap boundary, resultant length above `0.99`, and maximum absolute deviation at most `1.1°`.
- **SC-003**: An all-registration-invalid batch validates as strict JSON with zero observations and null descriptive values for all stability metrics.
- **SC-004**: Single and batch diagnostics plus summary contracts contain none of the forbidden measurement or candidate-status fields.
- **SC-005**: Full tests, Schema validation, static checks, immutable-core audit, and raw/large-file audit pass before delivery.
- **SC-006**: Documentation provides a runnable external Mac command without embedding or tracking any external asset.

## Assumptions

- Pixel center/radius distributions are diagnostic; normalized variants allow
  comparison when image dimensions differ.
- Percentiles use a deterministic continuous interpolation and are not quality
  thresholds.
- A one-frame distribution describes one observation only and cannot establish
  repeatability by itself.
- Real A2 stability values can be claimed only after the external Mac command
  runs; server synthetic data proves implementation behavior, not field
  performance.
- Corrected 19/30 truth remains a separate prerequisite for feature recovery
  evaluation and is not needed for this increment.
