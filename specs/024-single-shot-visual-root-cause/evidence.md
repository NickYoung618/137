# Evidence: 024 single-shot visual root cause

## Representative review

- Explicit nonsealed set: 9 images (145/147/141/161/441/281/261/401/374).
- Selection is by listed `imageId` only; `algorithmResultsUsedForSelection=false`.
- Git-external bundle contains 9 decodable overlays, one contact sheet, review JSON,
  candidate/circle/sidewall/failure/guidance CSV files and the Chinese diagnostic report.
- Archive SHA-256 before the bundled-core addendum:
  `6799624cae0a8cc81f9a71e44d03af60a8ca2f42f824fed6288277c667d2da13`.
- No detector threshold or PLC/HMI behavior changed in the diagnostic pass.

## Repository-contained legacy core

- Bundled module: `algorithms.end_face.core`.
- Bundled byte SHA-256:
  `f408631e03563ac80f392ea7558b786c2e2bef61670d1f206486f883b9ff8fbc`.
- Reviewed upstream gyj source SHA-256:
  `36a53cea8efd172cba0a06a4935b078ac77fd4551a509ed2c3519833fd206c35`.
- yyh production-integrated A-end-face source has the same byte SHA as gyj.
- The only diff between the bundled module and upstream source is two standalone CLI
  default filenames; circle, radial edge, polar and registration functions are unchanged.
- 41 focused adapter/contract/CLI/batch/subset tests passed. A dedicated temporary test
  loads the bundled module with annotation/reference assets under a temporary directory;
  no gyj/yyh path exists in that test. A wrong bundled SHA fails before image detection.
- The config Schema and portable example validate under Draft 2020-12.
- Server authoritative full discovery: 486/486 tests passed in 141.142s. The printed
  trace-output rejection is an expected fail-closed test path. All 48 root JSON Schemas
  passed Draft 2020-12 `check_schema`, and `git diff --check` passed.

## Real-image equivalence

The same frozen 022 detector configuration was changed only from external-source mode to
bundled-source mode. Git-external original BMPs 145 and 147 were rerun:

| Image | Current angle | Image correction | Physical circle `(cx,cy,r)` |
|---|---:|---:|---|
| 145 | 29.578393924928037 | +55.42160607507196 | (2811.194509469371, 1835.9268165342685, 1646.5589155894666) |
| 147 | 29.579343127253935 | +55.420656872746065 | (2811.1971748488286, 1835.9365522290682, 1646.6017776513806) |

Every listed value is exactly equal to the prior external-source JSON result. This proves
source packaging equivalence for these two development controls; it is not a production
accuracy claim.

## Remaining deployment asset boundary

The source code is now repository-contained. The A-end-face LabelMe reference and
reference image remain Git-external immutable deployment assets and must be supplied with
matching SHA-256 on Mac/production. This is intentional data governance, not a dependency
on the gyj code repository.

## Mac independent gate — 2026-08-17

- Candidate branch: `024-single-shot-visual-root-cause`; Mac validation branch:
  `024-mac-validation`; validated commit:
  `101f82f70e32aa2c527765247c3dadcc0f6edb67`.
- Focused suite: 41 tests ran, all passed; 3 were skipped by Mac environment conditions.
- Mac worktree remained clean. No threshold, main, PLC/HMI or sealed part-006 access
  occurred.
- Final Git-external diagnostic archive SHA-256 was independently verified as
  `000f64b6999c7ab38d24d9ae776dfdf98f3cc73ad27b85a54a3a46901a43038d`.
- Mac retained the original archive and created a separate Chinese-named human-review
  copy. Success controls and each failure class remain separated by sample/error type;
  this organization is for review only and does not create truth labels.

The engineering/Mac gate is accepted for 024. No aligned detector or threshold change is
safe before the following human semantic decisions:

1. 141/161/441: identify the physical housing outer edge.
2. 281: decide whether candidate-002 is the real square groove.
3. 261: decide which of candidate-004/candidate-006 is the real groove and whether the
   other is fixture-shadow evidence.
4. 401: decide whether both physical groove walls are visible.

374 remains the already confirmed mixed real-wall plus fixture-shadow negative and does
not require another semantic review.
