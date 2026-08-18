# Frozen Evidence and Threshold Baseline

## Repository boundary

- Branch: `027-groove-shadow-source-discrimination`
- Required ancestor: `d776c4d2f25b985fb4e50d4978cc3868cc59c6f7`
- Branch point/initial HEAD: `d776c4d2f25b985fb4e50d4978cc3868cc59c6f7`
- Forbidden: merge `main`; PLC/HMI modification or authorization; any read/run of sealed part-006.

## A2 observed diagnostic evidence

| Artifact | SHA-256 |
|---|---|
| Complete archive | `636fe9d786050e94e1f6d24515886c8434c2eca80268cff6d45c52c8085d1ae4` |
| `server-feedback-human-review.md` | `1a631b6ed198f1cb143855fc8eae5669f29c25532166ad6d5276257e5aab0c4a` |
| `server-feedback-human-review.json` | `5eec37621da8accb88a7db3136600735d35fd8fdcd6da0ecababa8e0f576dceb` |
| `technical-baseline-report.json` | `258df80a3a1f166e3689187eb241b7a891c5072f5fbd534f73905fa5e25e834f` |
| `failure-index.csv` | `508396ac608bfbe7045dac9520391165ac11cf6a6c16709ac9650e5512ff32be` |
| `overlay-index.csv` | `64a7bd43e486d68c96e069462defa2fe0d37fc9192022ef777ad10bff7e98187` |
| Mac runtime config | `d1dcb74b08acd29bcadff505c44586b04cfd2b712b75b5a9e2427f143b50a70c` |
| Normal results JSONL | `ec45c8ec6c8c00920aef015b2a5d9d3bf55c2f756072beb57b8c49624a43db66` |
| Bad-directory results JSONL | `026270c87aed0af4fa2180fd7e3c16ecb398b736a1b000428ffd710a6c1013e7` |

Data use is locked to `observed-diagnostic-not-unseen-acceptance`. The 700 images have no frozen per-image three-state human labels and no established physical grouping. Directory names and contact sheets are not truth labels.

## Locked effective gates from the Mac A2 config

- `min_polar_score = 3.0`
- recognition `threshold_version = groove-geometry-v1`
- recognition: local/edge contrast `20/15`, radial depth `35 px`, radial ratio `0.25`, paired support `0.55`, continuity `0.72`, width CV `0.185`, center drift `0.35`, groove score `0.62`, ambiguity margin `0.05`
- refinement `threshold_version = groove-sidewall-subpixel-v2`
- refinement: min side points `16`, min edge contrast/gradient `15/2`, max line P95 `2 px`, max intersection delta `2 deg`, consensus inlier/span/pair separation `0.5/0.7/0.25`
- original source consistency `threshold_version = sidewall-source-consistency-v1`: contrast `0.12`, gradient `0.35`, profile MAE `0.22`, profile correlation `0.75`, radial coverage `0.20`, endpoint structure `0.15`
- ambiguity resolution `schema_version = groove-ambiguity-resolution/1`, max candidates `3`

The Mac A2 replay left original source consistency and ambiguity resolution disabled. Therefore ambiguous-candidate physical/source evidence was not executed and must be reported as `not_evaluated`. Feature 027 must not alter any values above.

## Generated evidence

- Directory: `/home/ubuntu/disk/dzk/slot-pose-private-data/027-observed-diagnostic-trace-20260818-145000`
- `groove-shadow-source-report.json`: `4c2f3ac729f23dad147c6334faaba00bd3db84069d8e5381058188811689a11a`
- `failure-traces.csv`: `d099729141afa0973321c0978be92ae97a3475f1d74af42f4573af0c91517e13`
- Draft 2020-12 report Schema: PASS.
- Join: 207 rows, 207 unique image SHA values, no missing/duplicate/error-stage mismatch.
- Normalized terminal stages: candidate generation 6; recognition 74; ambiguity 46; polar quality 20; refinement 59; upstream outer circle 2.
- All 207 invalid results have null angle/direction/correction/mechanical/PLC outputs and `plcExecutionAuthoritative=false`.
- All 46 ambiguity frames have exactly two accepted coarse candidates and no executed per-candidate refinement/source evidence under the frozen Mac config.
- All 20 polar failures remain fail-closed; score range `2.8450255476506077..2.9275258930885655` against locked minimum `3.0`.
- Human three-state labels: 0. Safe-release/mixed-rejection counts remain null rather than inferred.
