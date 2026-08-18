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
