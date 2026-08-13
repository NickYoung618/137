# Tasks: A2 LabelMe Short-Line Reference

## Specification and design

- [x] T001 Record Mac A2 baseline and one-sample/20-frame development boundary.
- [x] T002 Document existing LabelMe mapping for 19/30 and related dimensions.
- [x] T003 Select external orientation-normalized gradient templates outside the core.

## Tests first

- [x] T004 Add strict LabelMe reference validation tests.
- [x] T005 Add domain-shifted external-template recovery and immutability tests.
- [x] T006 Add CLI/provenance/schema tests.

## Implementation

- [x] T007 Implement LabelMe short-line reference loader/catalog.
- [x] T008 Integrate optional external template into `ShortLineCandidateEvaluator`.
- [x] T009 Wire single-image, batch and compare CLIs.
- [x] T010 Extend JSON schemas and documentation.

## Verification

- [x] T011 Run full tests and Schema validation.
- [x] T012 Analyze spec-to-code/test traceability.
- [x] T013 Audit immutable core SHA and Git large-file/raw-asset boundary.
- [x] T014 Commit and push 137 main.
