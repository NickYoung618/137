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

The frozen observed-development evidence for runtime commit `005c32becf37f8d3a0e0e00dc6c8e7b504f0463a` is stored outside Git at:

```text
/home/ubuntu/disk/dzk/slot-pose-private-data/
  028-fixture-shadow-observed-development-20260818/final-005c32b/
```

It contains three result JSONL files, three complete review bundles, the 41-rejection enlarged contact sheet, repeatability/performance evidence, the six-image 026 comparison, and `final-observed-development-report.md`.

## 3. Visual review

Render all 140 overlays and contact sheets. Review every newly accepted or newly rejected transition, plus representative unchanged outcomes. A complete-near-shadow label requires visible non-overlap evidence; otherwise keep `INDETERMINATE`.

For fixture evidence, cyan marks the upper-small body/risk context and orange marks the lower-large false-source context. A lower-body candidate is never described as occlusion. Upper overlap is not sufficient for release: the review must also show the two-wall plus curved-floor U-contour evidence recorded by the runtime.

## 4. Compatibility and performance

Replay the six-image 026 set with recovery omitted and compare effective config identity and outputs. Run five same-adapter repeats on representative recovered and rejected frames; exclude only the first warmup and require warm P95 no more than 2.5 seconds.

The completed observed run retained effective config identity `ea29f321ffed31d3c410940833261cbc975a2f469efe4110bd93858ab3eaf657`; 168 focused tests and all 56 root schemas passed. Recovered 161 and rejected 401 both passed deterministic warm performance below 2.5 seconds P95.

## 5. Later 700-frame diagnostic

After upload, verify archive integrity, manifest count and image hashes. Freeze code/config before replay. The 700 images remain observed diagnostics and cannot support a production accuracy or PLC authorization claim.

Independent acceptance additionally requires a new physically separate part manifest with frozen human semantic labels. Do not reuse any of the seven 140-frame physical groups or any reviewed 700-frame part as unseen acceptance.
