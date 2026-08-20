# Quickstart: Sidewall Family Deduplication Validation

## Preconditions

- Branch and HEAD are recorded; worktree contains only intentional 031 changes.
- Corrected evidence archive SHA-256 is `d7de6d05f7af8066ca32065ffbc1d699850145b6af1504d5ed85a7d07bf2c5af`.
- `bad-0015` image SHA is `552022c13ed39948ea8ff9ee7d1f57af503df3b81df6bb9da41fbc08bd2b4823`.
- `bad-0102` image SHA is `d35b8ae88f7c5016fa7efa219e2e3271345f45d811c9a5f6bb0b3ee9c96513a3`.
- Do not access sealed part-006 or modify PLC/HMI.

## Focused Tests

```bash
python -m unittest \
  tests.test_groove_refinement \
  tests.test_slot_pose_contract \
  tests.test_legacy_adapter \
  tests.test_single_real_groove \
  tests.test_single_shot_initial_profile \
  tests.test_slot_pose_diagnostic_summary
```

Expected: same-source duplicates merge deterministically; separated, crossing, insufficient and nonfinite cases do not merge; v1 compatibility and all safety-null assertions pass.

## Schema Validation

```bash
python tools/validate_all_schemas.py
```

Expected: all root schemas validate, including the new strict wall-source diagnostic contract.

## Corrected Observed Regression

Run both corrected images once with the frozen v5 profile, then repeat each five times using one reused adapter.

Expected:

- `bad-0102` is valid only with radial two-wall, 5/5 curved-floor, normalized-profile and fixture-source proof; its original contrast/gradient failures remain in diagnostics beside the v3 adjudication.
- `bad-0015` remains invalid from independent mixed/occluded/source evidence.
- Every invalid result has null pose/correction/direction/mechanical/PLC command and non-authoritative PLC status.
- Repeat geometry and diagnostics excluding timing are identical.

## Performance and Broader Regression

After one warmup, record wall-family grouping time and end-to-end wall-clock P50/P95/max. Warm P95 must be at most 2.5 seconds. Replay the available observed cohort only after code/config are frozen; report transitions and failure stages without calling the cohort unseen acceptance or production accuracy evidence.

## Final Hygiene

```bash
git diff --check
git diff --cached --check
git status --short --branch
```

Do not merge main or authorize PLC. Production claims remain blocked until a physically separate new-part acceptance group passes.

## 2026-08-19 Handoff Evidence

- Final available test suite: `589/589 OK`; root schemas: `60/60` structurally valid.
- Corrected observed cases: `bad-0015` invalid 5/5 and `bad-0102` valid 5/5; each has one non-timing fingerprint.
- Warm algorithm elapsed P50/P95/max: `1216.122 / 1273.574 / 1278.400 ms`.
- Observed 140 compatibility: old valid 97/97 preserved; old mixed/occluded invalid 41/41 remain invalid; two old circle failures recovered by 029; final 99 valid / 41 invalid.
- Git-external evidence: `/home/ubuntu/disk/dzk/slot-pose-private-data/031-sidewall-family-dedup-validation/`.
- Physically separate new-part acceptance remains unavailable; accuracy, production readiness and PLC authorization remain prohibited.

## 2026-08-20 Observed A2-700 Convergence

- Frozen 031 replay: 506 valid / 194 invalid; physical outer circle accepted with one qualified edge family in 700/700 frames.
- High-resolution `CODEX_PREFILL — NOT HUMAN TRUTH` review covered all 24 wall-family-recovered valid frames and all 20 complete-visible `QUALITY_REJECTED` frames. It found 24 likely correct accepts and 20 likely false rejects pending human confirmation.
- The 20 suspected false rejects form one consecutive complete-visible groove sequence. Both walls and the floor are visible away from fixtures; only the unchanged global polar score fails at 2.845–2.928 against 3.0.
- Original 700-frame P95 remains recorded as 2614.638 ms and failed the 2.5 s gate. Stage evidence localized first-pass long tails to full-frame proposal/radial-edge extraction under server page/memory pressure, not wall-family grouping. A preloaded same-adapter two-pass replay of the original slow 42 had P95 1516.052 ms then 1949.265 ms with zero results over 2.5 s and identical outcomes.
- The prior 030 result JSONL with reported SHA `e87b5f186e1b0b86bc2d72b564c0fa31d8433aec868f01bbfbd52bfcd9377ba0` is not present on the server, so no per-image 030→031 transition table was fabricated; only aggregate differences are reported.
- Git-external evidence is under `/home/ubuntu/slot-pose-private-data/A2-700-observed-031-20260819/run-001/`, including `codex-review-44/`, `performance-root-cause.json`, and `030-031-transition-audit.json`.
- No recognition threshold was changed. A versioned safe treatment of global polar quality, if pursued, requires a separate specification because FR-010 keeps the current polar gate unchanged in feature 031.
