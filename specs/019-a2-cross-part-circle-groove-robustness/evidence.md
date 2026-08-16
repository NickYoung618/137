# Evidence: A2 跨零件圆与真槽鲁棒性

## Baseline

- Base: main@04d179628a6f3f7f2a30d2a4884ce5ef98abfffa
- Feature branch: 019-a2-cross-part-circle-groove-robustness
- Historical detector/config identity: 5c89563-era A2 700-image replay
- Sealed transitional sample: normal:part-006; execution consumed and excluded from all detailed reads/reruns/tuning
- Ground truth: one existing manually annotated reference only; no percentage accuracy is evaluated here

## Read-only root-cause baseline

The seven selected physical parts were joined to the historical results by the 009 confirmed
grouping and source SHA-256, not by JSONL line number.

| sample | historical outcome | stage evidence |
|---|---|---|
| normal:part-008 | 13 valid, 7 HOUSING_CIRCLE_NOT_FOUND | sparse residual boundary |
| normal:part-009 | 20 HOUSING_CIRCLE_NOT_FOUND | sparse residual systematic |
| normal:part-014 | 20 GROOVE_RECOGNITION_AMBIGUOUS | raw=3, accepted=2 |
| normal:part-015 | 20 GROOVE_RECOGNITION_FAILED | raw=2, accepted=0 |
| normal:part-019 | 20 GROOVE_RECOGNITION_FAILED | raw=0, dark threshold about -11 |
| normal:part-021 | 20 GROOVE_RECOGNITION_FAILED | raw=2, accepted=0 |
| normal:part-023 | 20 PHYSICAL_OUTER_CIRCLE_FAILED | sparse pass, final residual fail |

All 140 selected records produced three component proposals and exactly one eligible coarse housing
component. This is candidate/failure evidence, not circle or groove truth.

## Governance recovery

The main branch constitution had been replaced by the unrelated A-end-face measurement constitution
during a cross-repository merge. Commit 4284923 and the first parent of cf51782 retain the
slot-pose-specific constitution. Feature 019 restores those principles as v3.0.0 and records the
incompatible project-scope correction in its Sync Impact Report.

## Validation evidence

- Full gate: `uv run --with jsonschema python -m unittest discover -s tests -v` passed 345 tests in
  459.509 s. `/usr/bin/time -v` measured peak RSS 1,225,044 KiB and zero swaps. A concurrent unrelated
  vision process consumed substantial CPU, so wall time is not a production throughput measurement.
- Final focused Schema/integration gate passed 52 tests in 27.484 s; compileall, JSON parsing and
  `git diff --check` passed. Synthetic tests cover local/wrap circle pollution, distributed pollution,
  retained coverage, refit drift, negative MAD threshold recovery, cross-hypothesis dedup and 0/multiple
  groove fail-closed behavior.
- Selected seven-group historical audit completed without image replay: 700 lines scanned, 140 target records parsed,
  140 unique target SHA matched, sealedRecordsParsed=0, accuracyEvaluated=false, elapsed=398.897 ms.
- Three whole-sample folds: validation samples are [015,021,023], [009,019], and [008,014]; every sample/SHA
  intersection is zero. These are exposed development/validation folds, not strict test.
- External evidence SHA-256: fold-plan `0c384e951114675b8128a2d6f188147a0d0c7b56cbe2c345d418673e4ebac2d4`;
  audit `bcf24aa09b49c820f195901ce7aef7a5a5ea7a1db082c511bef28e4c6d80ea79`;
  groups CSV `406ff02105b37a0553c1da4c82ad4045fff69dd94cba9539814bc8f8d446b270`;
  14-item annotation queue `f6f9b664603479d348555e36678b041c6e7f2d3a76cae7bfe2dc842865199503`.
- External output is `slot-pose-evidence/a2-robustness-019-20260816/`; no absolute evidence path is committed.
- Same-machine paired diagnostic replay used the external 25-JPEG set only, never the 700 BMP set:
  default and experimental were both 25/25 detected with no current-angle/status change; experimental
  physical refit count was zero. Default internal elapsed P50/P95/max was 2350.2/3768.9/4117.5 ms and
  experimental was 2010.5/2908.9/2921.0 ms; both batch peak RSS values were 1,189,792 KiB. Cache order and
  concurrent load make these compatibility/resource observations, not an improvement or production timing claim.
  The host exposed 2 CPUs and about 7.5 GiB RAM; observed experimental P95 did not add 0.8 s, but the gate must
  be repeated on the deployment-equivalent idle machine before release.
- Experimental raw dark candidate count became 7/8 instead of 3 on those JPEGs, while downstream geometry
  still retained the unique real-groove path. Without independent per-candidate labels this cannot establish
  precision, recall or safe production activation.
- The server does not contain the seven target parts' original BMP pixels, so current code was not replayed on
  those 140 images. Mac must run each fold once after external config freeze; part-006 remains excluded.
- Spec Kit converge: 26 FR, 11 SC and 37 unique tasks were reviewed; all tasks and the 16-item requirements
  checklist are complete, with no clarification placeholder or unchecked task. No extra implementation task was appended.
- Final pollution gate: `git diff --check` and JSON parsing passed; added absolute server/Mac data paths=0,
  media/archive/JSONL files=0, added files over 1 MiB=0. All runtime media and reports remain outside Git.
