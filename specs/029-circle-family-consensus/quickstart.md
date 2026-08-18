# Quickstart: Validate Circle-Family Consensus

## Preconditions

- Use branch `029-circle-family-consensus` at the reported commit.
- Verify the frozen 140 image hashes before replay.
- Use only approved manifests; do not enumerate or access sealed part-006.
- Keep PLC/HMI untouched and treat every replay as offline diagnostic evidence.

## Focused validation

```bash
uv run python -m unittest \
  tests.test_physical_outer_circle \
  tests.test_full_frame_circle_locator \
  tests.test_slot_pose_contract \
  tests.test_circle_edge_family_trace \
  tests.test_single_shot_initial_profile
```

Expected: all focused tests pass, including version-1 compatibility, version-2 consensus, order/rotation invariance, ambiguity and non-convergence.

## Frozen real-image validation

Materialize a version-2 external config from the reviewed base, verify its SHA-256, and replay the approved 140-image manifests once. Expected:

- frames 442 and 449: one qualified family, accepted physical circle, and P95 `2.819/2.842 px` under unchanged gates;
- final observed total: `99` valid and `41` fail-closed;
- all 41 reviewed mixed/occluded grooves: `GROOVE_REFINEMENT_FAILED` with null pose and PLC command fields;
- an already-passing but downstream-sensitive family reports `not_needed` and preserves its previous circle and rejection;
- the other part-023 repeats receive the same image-only correction, with angle changes below `0.064 deg` and improved circle P95.

## Repeatability and performance

Reuse one adapter for at least one warm-up plus five measured runs of frames 442 and 449. Verify exact repeated geometry/diagnostic counts and warm P95 no greater than 2.5 seconds per image.

## Final checks

Validate every root JSON Schema, run `git diff --check`, record code/config/image/result hashes, and state that the 140 and later 700 images are observed diagnostics rather than independent production acceptance. Current engineering gate: 569 full tests pass, 57 root Schemas pass structural validation, 420 emitted family diagnostics validate, and recovered-path warm wall-clock P95 is below 1.37 seconds.
