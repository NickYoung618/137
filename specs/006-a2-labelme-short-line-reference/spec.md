# Feature Specification: A2 LabelMe Short-Line Reference

**Feature Branch**: `006-a2-labelme-short-line-reference`
**Created**: 2026-08-14
**Status**: In progress

## Evidence and scope

Mac A2 v2 first-25 evidence remains the immutable baseline: technical and localization both succeed 25/25, while core feature 19 and 30 are invalid 25/25 with `short_line_lateral_edge_not_found`. The existing v1 candidate uses the desktop reference image. The new field instruction is to use one physical sample at one position (20 repeated images) for development, create a manual LabelMe reference for the corresponding dimensions, and reserve all other physical samples for local validation.

This increment only changes the 137 A-end-face adapter and candidate path. It MUST NOT modify `algorithms/end_face/core.py`, overwrite legacy measurements or `coreValid`, access `caozitai`, or place raw images/large LabelMe files in Git.

## User scenarios

### US1 — Validate the A2 manual reference (P1)

An engineer marks features 19 and 30 as two-point `line` shapes in LabelMe on one representative image from one 20-frame A2 sample. A command validates labels, shape types, finite/in-bounds points, line lengths, referenced image dimensions and file hashes before any batch comparison.

**Acceptance**: malformed, duplicate, missing or out-of-bounds 19/30 annotations fail closed with an actionable error; a valid file produces an image-free JSON catalog.

### US2 — Use the A2 reference without changing the core baseline (P1)

The short-line candidate may use the manually annotated A2 image as its gradient-template source. Core detection still runs from the immutable desktop reference and its measurements/quality fields remain byte-for-byte untouched by candidate evaluation.

**Acceptance**: results identify whether the template came from the desktop reference or an external LabelMe reference and include annotation/image SHA-256; candidate geometry and `candidateValid` remain independent.

### US3 — Develop on one complete 20-frame sample (P1)

The compare CLI accepts the external short-line LabelMe reference and runs the existing per-image comparison on a manifest containing the complete 20-frame development group.

**Acceptance**: no tuning conclusion is considered traceable unless the manifest group has exactly 20 contiguous repeats and the selected physical sample does not appear in another split.

### US4 — Validate on all held-out samples (P2)

The same frozen reference and candidate configuration run on an external manifest for all remaining A2 samples. Outputs preserve per-image diagnostics and aggregate recovered/regressed counts.

**Acceptance**: full validation uses a different physical-sample set than development; raw images remain external.

## Functional requirements

- **FR-001**: Support an optional external LabelMe reference dedicated to candidate features 19 and 30.
- **FR-002**: Require exactly one canonical 19 line and one canonical 30 line, each with two finite, distinct, in-bounds points.
- **FR-003**: Require `imagePath`, `imageWidth`, and `imageHeight` to match an accessible external image.
- **FR-004**: Ignore embedded `imageData`; never copy it into outputs.
- **FR-005**: Preserve immutable desktop-core SHA, measurements, `featureQuality.*.coreValid`, localization and completeness semantics.
- **FR-006**: Record reference mode and SHA-256 provenance in single-image and comparison outputs.
- **FR-007**: Keep all existing signal, correlation, prominence, competing-peak, boundary and direction gates. An external reference MUST NOT force invalid candidates valid.
- **FR-008**: Provide an image-free annotation catalog suitable for diagnosing how each dimension is marked.
- **FR-009**: Retain backward compatibility when no external candidate reference is supplied.
- **FR-010**: Provide separate commands for a 20-frame development comparison and an all-held-out-sample comparison.

## Success criteria

- Synthetic tests prove that an A2-style external template can recover a domain-shifted 19/30 edge while the desktop template fails.
- Invalid LabelMe inputs fail before batch output is written.
- Existing v1 tests remain green.
- Schema validation, immutable-core SHA audit and Git large-file/raw-image audit pass.
- Mac evidence reports v1 versus LabelMe-reference candidate counts separately; no recovery claim is made from server synthetic data alone.
