# Research: Revoked Anchor and Annotation-Independent Registration

## R1 — Revocation boundary

**Decision**: reject the revoked annotation by SHA-256 in the shared loader
before parsing or image access.

**Rationale**: paths and filenames can change; the content fingerprint is the
only reliable cross-entry-point identity. Early rejection prevents accidental
template construction, tuning, or acceptance reuse.

**Alternative rejected**: documentation-only warnings are easy to bypass and
leave scripts capable of repeating invalid conclusions.

## R2 — Reference main-housing selection

**Decision**: choose the largest supported physical circle instance from the
reference image and require a configured radius margin over the runner-up.

**Rationale**: the main housing is the dominant complete circular instance in
the supported layout. This uses no short-line semantics. Existing center-cluster
deduplication prevents concentric rings on one housing from becoming false
runner-ups.

**Alternative rejected**: using 19/30 midpoint annulus membership contaminates
registration with the very annotation whose semantics are now untrusted.

## R3 — What remains testable

**Decision**: retain synthetic multi-instance, scale, rotation, ambiguity, and
strict-output tests; remove the external A2 self-anchor acceptance test.

**Rationale**: these tests validate geometry and failure protection without
claiming where physical dimension endpoints belong.

## R4 — Registration-only diagnostics

**Decision**: expose single and manifest batch modes that serialize input
fingerprints, hypotheses, checks, transforms, and failure reasons only.

**Rationale**: Mac can test instance selection and transform stability while
manual 19/30 truth is pending. Omitting candidate fields prevents registration
success from being misreported as measurement recovery.

## R5 — Real short-line resumption

**Decision**: corrected LabelMe is a mandatory future input and must pass the
existing strict shape/image validation plus the revocation gate. No automatic
endpoint fabrication or gradient snapping is added in this increment.
