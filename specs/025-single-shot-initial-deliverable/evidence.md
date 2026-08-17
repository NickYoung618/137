# Evidence: 单拍槽姿态初版交付

## SpecKit and implementation boundary

- Branch base: `024-single-shot-visual-root-cause@d853674`.
- Feature branch: `025-single-shot-initial-deliverable`.
- The first implementation increment adds one explicit Git-external profile materializer and report Schema.
- No detector threshold, image processing function, PLC/HMI behavior, main branch or sealed data changed.
- The profile requires repository-contained `algorithms.end_face.core`, single-groove pose v3,
  the unchanged complete 020 source-consistency thresholds, unchanged 022 adjudication,
  target 85°±5°, single capture and PLC mapping unconfirmed.

## Git-external profile and representative replay

- Materialized configuration SHA-256:
  `5cae955967d0893fa49176cd19606d298ede774731d1646a54598421b7bd9632`.
- Profile report SHA-256:
  `67d176f1db8ba05d64c8720332ba29fecf4ca2ef304dc77ca5a623de77915fd7`.
- Nine-result JSONL SHA-256:
  `338d7d0bbebc12481a4a63c1c7e228b19ae4bee0490cbf78f801ec0702e7f35a`.
- Dataset is the explicit nonsealed 024 representative manifest; no sealed part and no 700-image loop was read.
- Batch result: 9 total, 2 valid, 7 fail-closed.

| Representative | Result | Current angle | Image correction | Meaning |
|---|---|---:|---:|---|
| 145 | DETECTED | 29.578393924928° | +55.421606075072° CW | human-confirmed clean complete groove |
| 147 | DETECTED | 29.579343127254° | +55.420656872746° CW | human-confirmed clean complete groove; no independent circle truth |
| 141 | HOUSING_CIRCLE_NOT_FOUND | null | null | circle proposal/sparse physical gate |
| 161 | HOUSING_CIRCLE_NOT_FOUND | null | null | broader circle proposal/sparse physical disagreement |
| 441 | PHYSICAL_OUTER_CIRCLE_FAILED | null | null | sparse circle passes, final physical circle residual fails |
| 281 | GROOVE_RECOGNITION_FAILED | null | null | five raw dark candidates, none accepted |
| 261 | GROOVE_RECOGNITION_AMBIGUOUS | null | null | two groove candidates survive |
| 401 | GROOVE_REFINEMENT_FAILED | null | null | start-side wall consensus unavailable |
| 374 | GROOVE_SOURCE_INCONSISTENT | null | null | confirmed real-wall plus fixture-edge mixed negative |

All nine PLC command fields are null. The original source-consistency payload remains intact.
145/147 use `ACCEPTED_OVERRIDE`; 374 uses `REJECTED` and cannot release image guidance.

## Timing

The reused-adapter nine-image batch reported timing for the images that reached the timed detector
path: P50 `1998.153 ms`, P95/max `2274.444 ms`. This is below the current same-machine 2.5 s
single-image gate. A separate three-process cold parallel check took roughly 6.7–7.6 s per process
on the two-CPU server and is not a throughput or regression baseline; it demonstrates why production
batching must reuse one verified adapter/reference model instead of launching one process per image.

## Layered root-cause matrix and reuse decision

- **141**: the user confirmed that all three displayed circular edges are real housing circular
  edges. The coarse component exists near the expected shell, but sparse-ray residual P95 is
  `5.371 px` versus the scaled `5.316 px` gate; sector refit has 9 suspect sectors and retained
  coverage `0.694`. The next diagnosis must test whether rays switch between real concentric edge
  families or whether localization is biased; this is not evidence for relaxing the residual gate.
- **161**: the same human circular-edge conclusion applies. Sparse residual P95 `5.955 px`, 13
  suspect sectors and retained coverage `0.583` show broad disagreement, not a missing visible
  circle. Candidate/edge-family selection must be separated from acceptance-threshold behavior.
- **441**: the same human circular-edge conclusion applies. Sparse P95 `4.107 px` passes, final
  720-ray P95 `5.654 px` fails, with 19 suspect sectors and retained coverage `0.417`. The
  high-resolution stage exposes broad edge-family disagreement; the gate must not simply be relaxed.
- **281**: the user confirmed candidate-002 is fixture shadow, not the real groove. It is the only
  near-pass and fails `width_variation_too_high`; therefore the current zero-accepted result is safe,
  and widening that gate would create a known false positive.
- **261**: the user confirmed candidate-004 is the real groove and candidate-006 is fixture shadow.
  Their scores are `0.911` and `0.852`; the current fail-closed ambiguity is safe. The case may be
  used to diagnose missing square-opening/fixture rejection evidence, never as a candidate-ID rule.
- **401**: end wall has 27 support points; start wall has 19 detected edge points but no consensus
  support. The user confirmed both physical groove walls are not completely visible; the current
  refinement failure is the required initial behavior and must not be promoted.
- **374**: already confirmed one visible real wall plus a fixture-shadow edge. Existing endpoint
  structure difference `0.0764` exceeds the adjudication hard gate `0.05`; it remains the mandatory
  mixed-edge negative.

The current circle route already reuses the audited gyj/yyh outer-boundary ray sampling and robust
circle fit through the one repository-contained core. The groove route reuses that circle and the
existing subpixel edge/line/intersection implementation. No second copy or external runtime source
path is needed.

## Human semantic review resolved — 2026-08-17

- 141/161/441: all three displayed circular edges were judged to be real housing circular edges.
- 281: candidate-002 was judged to be fixture shadow, not the real groove.
- 261: candidate-004 was judged to be the real groove; candidate-006 was judged to be fixture shadow.
- 401: both real groove walls were judged not completely visible.

These are semantic decisions, not pixel truth. They close the prior identity questions but do not
authorize candidate-ID logic, runtime truth input or threshold relaxation. The next safe visual work
is circle edge-family trace analysis for 141/161/441 and fixture-shadow rejection diagnosis for 261;
281 and 401 are correct fail-closed controls.

## Engineering gates

- Focused single-shot/source-adjudication/closed-loop/single-groove/compatibility suite:
  `70/70` passed.
- Full server discovery: `492/492` passed in `123.695 s`.
- Root JSON Schemas: `49/49` passed Draft 2020-12 `check_schema`.
- Profile CLI help, JSON parsing and `git diff --check` passed.
- Changed-file scan found no private evidence root, Mac data root, representative image filename,
  image/archive or large derived artifact.
- The printed trace-output-outside-worktree error in full discovery is an expected tested
  fail-closed branch, not a test failure.

## Mac independent gate — 2026-08-17

- Mac validation branch: `025-mac-validation`; validated commit:
  `16f3d507af1330ad43eb5f233fb9e90a2c461ce5`.
- The explicitly requested three-suite command ran the tests present in that Mac checkout:
  `25/25` passed. This records the actual Mac count and does not claim that Mac reproduced the
  server-only `70/70` focused count.
- Mac worktree remained clean. No threshold, main, PLC/HMI or algorithm change occurred.
- The existing external human-review directory was reopened; no AUTO review mark was promoted to
  truth and no result was used for tuning.
- The Mac engineering gate is accepted. The former human semantic decisions were subsequently
  supplied and are recorded in the resolved review section above.
