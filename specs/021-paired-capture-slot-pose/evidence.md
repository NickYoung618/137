# Evidence: 021双帧配对槽姿态

## Baseline

- Parent branch: `020-fixture-shadow-groove-consistency@a964d56a7ffb2f47de6427679f602e28037e21e8`
- Feature branch: `021-paired-capture-slot-pose`
- Plain `uv run python -m unittest discover -s tests -v`: 359 tests ran; two import errors were solely the missing optional `jsonschema` package in the plain environment (`test_current_capture_contract`, `test_current_capture_real_e2e`), with 19 skips. This is an external dependency gate, not an algorithm regression.
- Authoritative full gate uses `uv run --with jsonschema ...`.

## SpecKit Analyze

- Buildable requirements: 34 (25 FR + 9 SC)
- Tasks: 22
- Requirement coverage: 100% at story/task level
- Critical Constitution conflicts: 0
- Unresolved behavior ambiguity: 0; unknown现场 rotation values are represented by `UNCONFIRMED` state.

## Data and Truth Boundary

- No real paired BMP is available on the server; no real paired accuracy claim is possible.
- Sealed `normal:part-006` was not read or rerun.
- `Pic_2026_08_13_132354_292.bmp` remains skipped.
- part-019 374/369 are the active review targets, but their media and generated review artifacts remain outside Git.
- Existing 132112_4 manual outer arc/groove boundary may be used only as a development reference and never as runtime input.

## Final Verification

- Focused paired/review tests: `26 tests`, all passed.
- Authoritative full gate: `uv run --with jsonschema python -m unittest discover -s tests -q` ran `391 tests` in `107.311s`; all passed.
- JSON and Schema syntax, Python compile, both CLI help entry points, and `git diff --check`: passed.
- New-file large-media scan found no file over 1 MiB; changed-content scan found no Mac/server evidence absolute path.
- Worst-case bounded 16x16 pure matcher microbenchmark (`n=1000`, excludes both single-frame detectors): P50 `1.826188ms`, P95 `2.172057ms`, max `4.876364ms` on this server. Real paired BMP end-to-end timing remains a Mac gate.
- Default example remains `enabled=false`; `UNCONFIRMED` rotation cannot produce image guidance, and PLC execution remains not authorized even after a confirmed diagnostic match.
- `main` and `origin/main` were both `04d179628a6f3f7f2a30d2a4884ce5ef98abfffa` before feature-branch commit/push. No main merge is authorized for 021.

## Simplified Manual Review Convergence

- Scope: part-019 374/369 review presentation only. No detector, threshold, paired matching, default configuration or PLC code changed.
- The prior v1 review bundle exposed the full 019/020 debug overlays, fitted circle and every raw ray. Revised `slot-pose-prefill-review/2` emits only full-resolution raw/simplified, a two-column contact sheet and minimal AUTO_ LabelMe.
- Simplified layers are limited to 019 final left/right walls and mouth endpoints plus 020 observed dark angular intervals. Pair identity selection uses only `pairEvidence.selectedCandidateIds`; incomplete/not-matched evidence is never filled by the nearest candidate.
- A raw start/center/end is rendered as an open orange circumference bracket with three ticks. It is explicitly labelled `Observed dark angular interval / Fixture identity unconfirmed / Pixel boundary unknown`; only missing intervals degrade to a direction arrow. No polygon or filled region is emitted.
- TDD red gate: the new focused test initially failed because the simplified text/render contract did not exist. Green gate: paired/review focused suite ran `26 tests` in `0.111s`, all passed.
- Authoritative full gate after the review change: `391 tests` in `105.935s`, all passed.
- Schema JSON, CLI help, Python compile and diff checks passed. The review test verifies two rows, original-resolution simplified PNG, stable colors, interval/direction downgrade, no nearest-unmatched identity, no filled region, no overlay directories, and no fitted-circle/raw-ray/rectangle/truth labels.
- Real 374/369 BMPs are not available on the server, so no generated image is committed and no visual correctness claim is made here. Mac must generate the Git-external bundle and the user must confirm the true groove and same-source walls.

## 2026-08-16 Single-frame Local Second-wall Convergence

- Human semantic feedback is recorded without pixel-truth inflation: the top square opening is the real groove region; 019 hit at least one real wall/region but paired its second wall with the upper-right fixture shadow. The feedback does not define exact wall pixels, mouth endpoints or fixture boundaries.
- Added optional `detector.local_second_wall_diagnostic`; omission and `enabled=false` preserve the prior effective/default runtime path. Enabling requires single_real_groove, refinement v2 and the unchanged enabled 020 source-consistency gate.
- The search reuses the existing subpixel tangential sampler, deterministic consensus TLS wall fit and sidewall profile consistency. It scans at most 48 configured seeds inside the coarse local interval and retains every side-search candidate and every pair hypothesis with failed checks.
- Hard layers are `candidate_anchor`, `local_geometry` (interval, width, parallelism, radial coverage), `mouth_endpoint` (same physical-circle residual), `opening_structure` (dark connected support), `sidewall_source` (contrast/gradient/profile/endpoint structure), and uniqueness. Diagnostic score cannot override any failed hard gate.
- Failure inventory is explicit: `CANDIDATE_MISSING`, `LOCAL_SECOND_WALL_NOT_FOUND`, `MULTIPLE_LOCAL_OPENINGS`, and `SOURCE_INCONSISTENT` with `failureStage`.
- `UNIQUE_DIAGNOSTIC` is never authoritative: `authoritative=false`, `posePromotionAllowed=false`. A runtime integration test forces a unique experimental result and verifies that the surrounding output remains `GROOVE_SOURCE_INCONSISTENT`, `valid=false`, with null image correction and no PLC command.
- Synthetic tests cover arbitrary rotations including 0/360, real grooves near 31°/328°, endpoint reversal via wrap, brightness reduction, additional blur, unequal fixture contrast/width/depth, partial overlap, multiple openings and missing second walls. Controlled brightness/blur cases assert each endpoint error <0.15° and midpoint error <0.10°.
- The part-019 file names, angles and coordinates are absent from runtime code/config. Sealed part-006 was not read or rerun. Existing 132112_4 manual reference was not used as runtime input and still cannot support an accuracy percentage.

## 2026-08-16 Final Gates for This Increment

- SpecKit analyze: 42 FR, 13 SC, 38 tasks; no placeholder, critical Constitution conflict or uncovered new implementation task. Two stale “fixture region” phrases were reconciled to the angular-interval contract before the final run.
- Focused gate: 57 contract/runtime/review/local-wall tests passed before deformation expansion; final local-wall suite contains 10 passing tests.
- Authoritative full gate: `uv run --with jsonschema python -m unittest discover -s tests -q` ran 405 tests in 111.673s; all passed.
- All JSON parsed; all root contract Schemas passed Draft 2020-12 meta-validation; Python compile, both affected CLI help commands and `git diff --check` passed.
- Changed-content scan found no new server/Mac absolute data root, evidence root or A2 archive path. Relevant source/spec/test trees contain no file over 1 MiB and no BMP/JPEG/PNG/MP4/RAR/ZIP.
- Server has no 140 original BMP validation set, so Mac three-fold replay remains required. The quickstart reports top-level valid, experimental candidate status and failure inventory only; it explicitly forbids calling these counts accuracy.
- `main` and `origin/main` remain `04d179628a6f3f7f2a30d2a4884ce5ef98abfffa`; this increment is feature-branch only and must not merge main.

## Mac 140-frame Replay at 8ff3889

- Mac used 140 nonsealed original BMPs and the existing three validation manifests. Experimental config SHA prefix was `79960702`; server does not possess these BMPs or JSONL and did not rerun them.
- Top-level valid remained 0/140. The earlier 33 `GROOVE_SOURCE_INCONSISTENT` frames ran local diagnostics; the other 107 failed upstream and remained `NOT_RUN`.
- All 33 local runs were `SOURCE_INCONSISTENT`: part-019 20 frames and part-008 13 frames. Each part-019 record had 48 side search entries and one final hypothesis.
- The only part-019 hypothesis still failed `sidewall_source_consistency / edge_contrast_asymmetry`; 374/369 contrast normalized difference remained approximately 0.127–0.138 against the unchanged 0.12 gate while other reported gates passed.
- Human interpretation is unchanged: the hypothesis appears to reproduce the known real-wall plus upper-right fixture-shadow mixed pair. Therefore this replay is not a recovery and is positive evidence against relaxing 0.12 to 0.14.
- Required next evidence is pre-threshold generation trace: inherited local interval, both anchors, every seed fit/rejection, side merge clusters and hypothesis merge clusters. No accuracy or valid-rate improvement is claimed.

## Candidate-generation Trace Increment

- Diagnostic output advances to `local-second-wall-diagnostic/2`; config schema and every numerical threshold remain unchanged. The 0.12 contrast gate, ±4° tangential search, minimum support and 0.5° merge threshold were not relaxed.
- Each anchor now records original endpoint angle, required opposite polarity, finite line segment, support, contrast, gradient and local profile. `localInterval.source=coarse_raw_dark_candidate` makes inherited mixed intervals explicit.
- Every seed records its search window, polarity, detected points, rejection stage (`EDGE_SAMPLING`, `LINE_CONSENSUS`, or `OUTER_CIRCLE_INTERSECTION`), fit angle/delta, line/finite segment, failed checks and merge disposition.
- Side merge clusters preserve all member/suppressed IDs, seed/fitted angles, spread, representative and the unchanged v1-compatible selection rule. Pre-merge hypotheses and hypothesis clusters similarly permit exact member accounting.
- Per-polarity summaries classify `NO_EDGE_SIGNAL`, `SINGLE_EDGE_ATTRACTOR`, or `MULTIPLE_EDGE_CLUSTERS`. This is diagnostic evidence only; it does not select a more permissive pose.
- Added a path-free `local-second-wall-trace-export/1` CLI. It selects exact image basenames from one or more JSONL files and emits no image pixels, absolute paths or human truth; output is required to remain Git-external and explicitly forbids threshold tuning.

## Verification for Candidate-generation Trace

- Focused local-wall/trace tests: 14 tests passed. Broader focused runtime/contract/review gate: 64 tests passed; the printed Git-internal-output error is an expected negative safety test.
- Full suite ran 409 tests. 408 passed; the only failure was the pre-existing legacy wall-clock assertion `<8.0s`, measured at 15.93s. An isolated rerun measured 16.00s and failed the same timing-only assertion.
- During both timing measurements, an unrelated protected-repository four-worker image batch occupied all available CPUs at roughly 30% CPU per worker. The failing legacy path does not contain or execute the default-off local diagnostic. The 8-second gate was not modified or waived; a clean-load rerun remains required before claiming the full gate passed.
- JSON parsing, all root Draft 2020-12 Schema meta-validation, Python compile, trace CLI help, diff, media/large-file and new absolute-data-path checks passed.
- After that external batch finished, the isolated unchanged legacy timing gate passed in `3.443s` against the original `<8.0s` assertion. A clean-load authoritative rerun then executed all `409 tests` in `109.561s`; all passed. No performance threshold, detector threshold or default configuration was changed to obtain this result.
