# Quickstart: Physical-Groove Polar Quality Adjudication Validation

## Preconditions

- Work on `codex/032-polar-quality-adjudication`, based on the frozen 031 implementation.
- Runtime result metadata uses algorithm version `0.20.0`; 031 remains `0.19.0`.
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
- Materialized profile-v6 config SHA-256:
  `395b6710c5b40b23d62f00a1b6d8daad6c14ec2815ebb3b72d62aeb80b33b1b4`.
- Materialized profile report SHA-256:
  `832f533be9e8b3be582bcd70af54fdee0c985e22919d6fee4abd759ebab46a3f`.

Two pre-freeze batch attempts were intentionally terminated before producing
accepted evidence: one exposed stale algorithm-version metadata and the second
had loaded runtime code before the final malformed-evidence fail-closed patch.
Their directories are explicitly prefixed `aborted-`; neither may be counted.
