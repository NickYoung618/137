# Quickstart: Physical-Groove Polar Quality Adjudication Validation

## Preconditions

- Work on `codex/032-polar-quality-adjudication`, based on the frozen 031 implementation.
- The frozen 032 replay used algorithm version `0.20.0`; the additive visible-boundary
  source fix uses `0.21.0`. 031 remains `0.19.0`.
- Preserve `min_polar_score=3.0` and every other recognition/refinement/source/fixture/circle threshold.
- Keep all A2 images and review artifacts outside Git and identified by SHA-256.
- Do not access sealed part-006, modify PLC/HMI or merge main.

## Focused Validation

The only supported opt-in object is:

```json
{
  "schema_version": "polar-quality-adjudication/1",
  "enabled": true,
  "strategy_version": "locked-physical-groove-proof-v1",
  "development_only": true
}
```

Omission or `enabled=false` adds no runtime diagnostic and preserves the prior
quality decision. Profile v6 is additive; profiles v2 through v5 remain
unchanged. The decision is rejected at config load outside single-groove v3 or
without the reviewed circle-family, refinement, ambiguity, source, fixture and
shadow-source dependencies.

Run the pure decision, contract, adapter, single-groove, profile and diagnostic-summary tests. Expected outcomes:

- sole `polar_score` plus every physical proof -> `ACCEPTED_OVERRIDE`;
- threshold equality or no original failure -> `NOT_NEEDED`;
- each missing proof, second failure, ambiguity, mixed/occluded or nonfinite input -> no release;
- omitted/disabled configuration -> prior result unchanged;
- original polar score, threshold and failure remain visible for every decision.

## Observed Regression

Frozen observed evidence (diagnostic only):

- root: `/home/ubuntu/slot-pose-private-data/A2-700-observed-031-20260819/run-001`;
- 031 result JSONL SHA-256: `6e0e65eb9b0d3dfd6b8e558c24aae1eb8380c6c0c591d8ce671ca74b615230c3`;
- CODEX pre-review CSV SHA-256: `95c47547d58097cc899abcbcb8dedb6f7f700a126a153e5ed80b1da2469f5d15`;
- performance root-cause SHA-256: `f6a26568b5804f18ce1d38f318fe41b71bf3cfe65ef72ea60a67b89b48cab7a7`;
- 030→031 transition audit SHA-256: `f92b1ec993849a58e800a8982af84bcc67e628dfb40f4b21aecbbde5c62f2c27`.

The original first-pass 700-frame warm-excluding-first wall-clock P95 was
2614.638 ms and remains a recorded failed performance observation. It must not
be replaced by later preloaded steady-state measurements.

With code/config frozen, replay only the approved observed manifests:

- the 20-frame complete-visible sequence may become valid only through the v1 adjudication and must retain original `polar_score` failure evidence;
- the 24 prior wall-family-recovered valid frames remain valid;
- all 174 runtime mixed/occluded frames remain invalid with complete safety nulls;
- physical circle remains accepted with one qualified family in all 700 frames.

This replay is diagnostic, not accuracy evidence. Human confirmation and physically separate new-part acceptance remain pending.

## Repeatability and Performance

Repeat one released and one denied case five times with a reused adapter. Non-timing decisions, proof fields and pose/null outputs must be identical. After warmup, P95 must not exceed 2.5 seconds and the new decision must show no additional image load or analysis pass.

## Final Gates

- Focused and full available tests pass.
- All root schemas validate.
- `git diff --check` and `git diff --cached --check` pass.
- Report branch, commit, config/result hashes, observed versus new-part evidence, and clean worktree status.
- Do not claim production accuracy or authorize PLC before physically separate acceptance.

The physically separate new-part acceptance group is currently **PENDING**.
Until its manifest, human truth and replay are independently reviewed, this
feature is development-only and no accuracy-improvement, production-readiness
or PLC-authorization statement is permitted.

## 2026-08-20 Pre-Replay Freeze

- Focused new decision/config/adapter/summary/profile tests: 13/13 passed.
- Full available test discovery with `jsonschema`: 604/604 passed in 120.830 s.
- Root Draft 2020-12 Schema structure gate: 62/62 passed.
- `git diff --check`: passed.
- Representative bad-0041 result SHA-256:
  `b04712e47ca2966c7e1d6e152c59f901bb0c0913eba894f532e40993b716cc77`.

## 2026-08-20 Frozen Observed Replay

- Frozen implementation commit: `98a984a5f04b18d8b1a8f9e9fb3188eb897b0cb9`.
- Frozen v6 config SHA-256: `395b6710c5b40b23d62f00a1b6d8daad6c14ec2815ebb3b72d62aeb80b33b1b4`.
- Result JSONL SHA-256: `e19b492cae413eefa805153ff53d7cddf7a838b7fcbad8e4955d8160cab0fb77`.
- Results: 526 valid, 174 invalid. The exact transitions from 031 were 506
  valid-to-valid, 20 invalid-to-valid and 174 invalid-to-invalid, with no
  valid-to-invalid transitions.
- All 20 changed outcomes were prior sole-`polar_score` quality rejects and
  retained the original score, threshold and failed check while passing all 11
  independent physical proof checks.
- All 24 prior wall-family-recovered valid frames remained valid. All 174 prior
  runtime mixed/occluded frames remained invalid. The physical outer circle was
  accepted with exactly one family in all 700 frames.
- Invalid safety violations: zero. Non-null PLC commands: zero. Authoritative
  PLC results: zero.
- First-pass algorithm elapsed P95 across 700 frames: 1281.043 ms.
- Five repeated released and denied cases were identical after excluding all
  timing fields. One image decode occurred per estimate, with no second circle,
  polar, recognition or refinement pass. Combined algorithm-only warm P95 was
  980.793 ms. Full wrapper wall time is separately retained because result
  assembly, validation, hashing and large diagnostic copying are outside the
  adapter algorithm timer; the denied representative wrapper P95 was 3189.554
  ms and is not hidden.
- Git-external evaluation summary SHA-256:
  `37a606a39c5c15cd09c8c2c32321c93f1cb2d5871dbbf7ea6901ced352cccadb`.
- Git-external repeatability summary SHA-256:
  `52366e56d0c3723738968775e75113126d3ffd721d77498b11118dd63a0e72b0`.

This remains observed diagnostic evidence, not unseen acceptance or an accuracy
claim. Physically separate new-part validation remains pending.

## Final Convergence Status

- Branch: `codex/032-polar-quality-adjudication`.
- Frozen implementation commit: `98a984a5f04b18d8b1a8f9e9fb3188eb897b0cb9`.
- Full available tests at the frozen implementation: 604/604 passed.
- Final root Schema structure gate after replay documentation: 62/62 passed.
- Final `git diff --check` and `git diff --cached --check`: passed.
- SpecKit convergence checked all functional requirements, success criteria,
  user-story acceptance cases, plan decisions and five Constitution principles;
  no missing implementation task was found and no convergence task was appended.
- Worktree before this final documentation commit: modified only in `quickstart.md`
  and `tasks.md`; no runtime, config, threshold, PLC/HMI or main change was made.
- Materialized profile-v6 config SHA-256:
  `395b6710c5b40b23d62f00a1b6d8daad6c14ec2815ebb3b72d62aeb80b33b1b4`.
- Materialized profile report SHA-256:
  `832f533be9e8b3be582bcd70af54fdee0c985e22919d6fee4abd759ebab46a3f`.

Two pre-freeze batch attempts were intentionally terminated before producing
accepted evidence: one exposed stale algorithm-version metadata and the second
had loaded runtime code before the final malformed-evidence fail-closed patch.
Their directories are explicitly prefixed `aborted-`; neither may be counted.

## 2026-08-20 Visible-Boundary Source Convergence

- The user visually confirmed `bad:0161`, `normal:0001` and `normal:0243` as
  complete and unoccluded. Read-only traces showed accepted circle, recognition
  and two-wall geometry; their terminal source rejection came from photometric
  asymmetry, a recovery-proof schema mismatch, or angular fixture proximity
  without visible interruption.
- Algorithm `0.21.0` adds default-off
  `source-consistency-adjudication/4` with strategy
  `locked-visible-boundary-ownership-v4` and profile v7. No recognition,
  refinement, source, ambiguity, polar, fixture or circle threshold changed.
- The v3 compatibility defect now follows the actual recovery evidence schema,
  not the number of failed photometric scalar checks. V4 additionally records
  `sourceSeparationBasis` as `complete_u_contour`, `recovery_verified` or
  `visible_boundary_ownership`. Fixture-source evidence `/3` records two visible
  walls, a present center floor track and bounded partial-track support; angular
  proximity alone is insufficient.
- Focused source/fixture/profile/config tests: 74/74 passed. Full available
  tests: 608/608 passed. Root Draft 2020-12 schema structure checks: 63/63
  passed. `git diff --check` passed.
- Git-external evidence root:
  `/home/ubuntu/slot-pose-private-data/A2-700-observed-033-diagnostic-20260820`.
  V7 config SHA-256 is
  `74baa2062db6724d333e6d529717036a6c61add28019fc5f0a9329c51b386e85`;
  final 700-result SHA-256 is
  `b83865001cd04a6ea36d938de6b1d3ad9cf8e0e8873b6791556a62c3c4dbfe3b`.
- The frozen observed replay contains 700/700 results and 0 image-SHA
  mismatches: 618 valid and 82 invalid. Relative to frozen 032, transitions are
  526 valid-to-valid, 92 invalid-to-valid, 82 invalid-to-invalid and zero
  valid-to-invalid. The 92 releases use 76 complete-U-contour proofs, one
  recovery proof and 15 visible-boundary-ownership proofs.
- Confirmed targets `bad:0161`, `normal:0001`, `normal:0243` are valid. The
  visually confirmed truly occluded control `bad:0001` remains invalid. The 41
  images in the previously reviewed upper-small-circle occlusion index align
  by source filename to this replay and remain 41/41 invalid (40 refinement,
  one source consistency).
- All 82 invalid results retain null angle, correction, direction, mechanical
  and PLC fields with PLC non-authoritative. Across all 700 results, non-null
  PLC commands and authoritative PLC results are both zero.
- Five same-adapter repeats of the released `bad:0161` and denied `bad:0001`
  have identical decision, geometry and safety outputs. Dedicated uncontented
  warm algorithm P95 is 1130.740 ms for the released case and 1076.165 ms for
  the denied case. The four-way replay elapsed timings are intentionally not a
  performance gate because the workers shared CPU.
- A first monolithic run and an early chunked run produced no accepted final
  evidence; the latter is retained under `aborted-code-changed-after-start`
  because a diagnostic-consistency correction occurred after it began. Only
  the subsequent frozen 35-chunk replay was concatenated into `final-results.jsonl`.
- This remains observed A2 diagnostic evidence. Only three newly human-confirmed
  complete cases and the prior 41-image occlusion index have semantic authority;
  the other runtime classes are not human truth. Physically separate new-part
  acceptance remains pending, so no production-accuracy, readiness or PLC claim
  is allowed.
