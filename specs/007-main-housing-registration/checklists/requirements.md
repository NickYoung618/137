# Specification Quality Checklist: Main Housing Registration

**Purpose**: Verify that feature 007 is implementable, testable, and bounded  
**Created**: 2026-08-14  
**Feature**: [spec.md](../spec.md)

## Content quality

- [x] User-visible instance selection, registration, candidate, and Mac workflows are stated.
- [x] The withdrawn single-image endpoint result is explicitly excluded from all claims.
- [x] No implementation placeholders or unresolved clarification markers remain.
- [x] External raw images and result JSONL are excluded from Git scope.

## Requirement completeness

- [x] Core immutability and legacy-output immutability are explicit.
- [x] The old transform is prohibited as the v2 search seed.
- [x] Fail-closed support, ambiguity, scale, rotation, and frame gates are testable.
- [x] v1 compatibility and v2 independent transition semantics are specified.
- [x] External annotation and image provenance are pinned.

## Readiness

- [x] Acceptance criteria cover synthetic multi-instance, failure, schema, and corrected-truth deferral paths.
- [x] The Mac 25-frame command is required without assuming its result.
- [x] Core SHA and large-file/raw-image audit gates are identified.

## Notes

All specification checks pass. No clarification is required before planning.
