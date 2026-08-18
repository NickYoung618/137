# Quickstart: Fixture-Shadow Root-Cause Recovery

## 1. Focused tests

```bash
uv run python -m unittest \
  tests.test_groove_recognition \
  tests.test_groove_refinement \
  tests.test_source_consistency_adjudication \
  tests.test_groove_shadow_discrimination \
  tests.test_single_real_groove \
  tests.test_slot_pose_contract -v
```

Expected: all tests pass; default-off tests prove prior outputs/config identity remain unchanged.

## 2. Frozen 140-frame observed replay

Run the three approved manifests separately with one reviewed Git-external config and write outputs outside the worktree. Verify each manifest has twenty frames per listed physical sample and no image hash mismatch. Never treat the result as independent acceptance.

Expected report sections: old/new transition counts, terminal-stage counts, provisional/accepted/rejected candidates, wall-family outcomes, original/effective source decisions, four-state classification, timing, and invalid-output safety.

## 3. Visual review

Render all 140 overlays and contact sheets. Review every newly accepted or newly rejected transition, plus representative unchanged outcomes. A complete-near-shadow label requires visible non-overlap evidence; otherwise keep `INDETERMINATE`.

## 4. Compatibility and performance

Replay the six-image 026 set with recovery omitted and compare effective config identity and outputs. Run five same-adapter repeats on representative recovered and rejected frames; exclude only the first warmup and require warm P95 no more than 2.5 seconds.

## 5. Later 700-frame diagnostic

After upload, verify archive integrity, manifest count and image hashes. Freeze code/config before replay. The 700 images remain observed diagnostics and cannot support a production accuracy or PLC authorization claim.
