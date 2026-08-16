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
- Simplified layers are limited to 019 final left/right walls and mouth endpoints plus 020 fixture A/B candidates. A matched angular extent is an orange candidate region; a non-matched/insufficient extent is an orange short direction arrow. Both remain candidate-only and do not change 020 valid.
- TDD red gate: the new focused test initially failed because the simplified text/render contract did not exist. Green gate: paired/review focused suite ran `26 tests` in `0.111s`, all passed.
- Authoritative full gate after the review change: `391 tests` in `105.935s`, all passed.
- Schema JSON, CLI help, Python compile and diff checks passed. The review test verifies two rows, original-resolution simplified PNG, stable colors, exact minimal labels, region/direction downgrade, no overlay directories, and no fitted-circle/raw-ray/rectangle/truth labels.
- Real 374/369 BMPs are not available on the server, so no generated image is committed and no visual correctness claim is made here. Mac must generate the Git-external bundle and the user must confirm the true groove and same-source walls.
