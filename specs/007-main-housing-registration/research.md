# Research: Main Housing Registration

## R1 — Root-cause evidence

The old A2 predictions are not local misses: feature 19 lands in metal texture
and feature 30 lands in a black opening because the legacy global transform is
biased toward the right-hand neighbor. Expanding or weakening the old +/-24 px
search would search the wrong physical instance and is rejected.

## R2 — Instance proposal method

**Decision**: enumerate foreground connected components on a configurable
downsampled image, form circle proposals from near-square component bboxes, and
refine them with full-circle radial material-to-background edge samples.

**Rationale**: the A2 representative contains one dominant complete main
housing and smaller/cropped circular neighbors. Component enumeration produces
multiple explicit hypotheses without OpenCV, while robust radial fits avoid
treating a component bbox as final geometry.

**Alternatives rejected**:

- Reuse the core transform: directly contradicted by A2 evidence.
- Global phase correlation: can align the entire multi-part scene to the wrong
  repeated circular structure.
- Add OpenCV Hough circles: adds an unpinned dependency and still requires
  explicit instance selection.

## R3 — Reference instance selection

**Decision**: require both manual 19/30 midpoints to lie within a configured
annular fraction of a refined reference circle. Rank qualifying proposals by
circular support and residual.

**Rationale**: the manual coordinates identify which physical instance is the
main housing without inventing additional labels. Target selection never uses
target core geometry.

## R4 — Rotation

**Decision**: correlate normalized annular angular gradient signatures after
center/scale fitting; require peak score and a separated runner-up margin.

**Rationale**: circular geometry provides no angle. Annular appearance retains
notches and stepped/engraved asymmetry, while a separate ambiguity gate rejects
repeated ring patterns.

## R5 — Local feature recovery

**Decision**: transform the true external 19/30 endpoints, then reuse the
existing v1 bounded template correlation, texture, gradient, prominence,
competing-peak, boundary and angle gates.

**Rationale**: the failure is primarily global instance registration. Reusing
strict local gates changes the search origin without lowering acceptance
thresholds or declaring every projected edge valid.

## R6 — Real-data claims

The external representative is an anchor/identity smoke test only. The Mac
must run the frozen v2 configuration over all 25 external frames before any
recovery-rate claim. JSONL and images remain outside Git.
