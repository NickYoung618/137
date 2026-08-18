# Phase 0 Research: Fixture-Shadow Root-Cause Recovery

## R1 — Frozen 140-frame evidence

**Decision**: Treat the seven groups (`part-008`, `009`, `014`, `015`, `019`, `021`, `023`) as an observed development regression cohort. Preserve the original d776 result and the 027 result for every image SHA.

**Rationale**: The replay found 20 recognition rejections, 44 refinement failures, 54 source-consistency failures, two circle failures and twenty valid results. The folder class is not semantic truth, so retained failures require explicit evidence rather than being counted automatically as wrong.

**Alternatives considered**: Calling 140 independent acceptance was rejected because all images and outcomes are already observed. Counting frames as 140 independent parts was rejected because they are seven physical groups.

## R2 — Recognition recovery is provisional, not threshold relaxation

**Decision**: Add a default-off versioned recovery strategy that may forward a candidate rejected only by `width_variation_too_high` when every other original recognition check passes. It remains provisional until unique wall-family refinement and effective source consistency pass.

**Rationale**: All twenty `part-015` frames generate five raw candidates; the plausible candidate fails only width variation while retaining outer connection, depth, contrast, paired support and continuity. Raising the global width-CV threshold would also admit unrelated shadow candidates. Downstream physical proof provides an independent discriminator.

**Alternatives considered**: Raising `max_width_coefficient_of_variation`, lowering recognition score, or selecting the best score were rejected as global relaxation or ranking without physical proof.

## R3 — Multi-peak wall families replace strongest-peak commitment

**Decision**: In refinement v3, sample each radial row once, retain a bounded set of polarity-correct tangential edge peaks, and form deterministic cross-radius wall hypotheses. Require one unique family per side using the existing minimum support, inlier ratio, longitudinal coverage, residual, intersection/search margin and support-margin semantics. Only selected observed points enter the final TLS line and outer-circle endpoint computation.

**Rationale**: `part-009` and `part-021` contain strong evidence on both walls, but choosing the strongest peak independently per radius switches to nearby shadow/texture edges. The resulting point cloud either intersects beyond the coarse boundary gate or has no straight consensus. A global family decision addresses the source of the inconsistency without lowering any gate.

**Alternatives considered**: Increasing intersection delta, decreasing minimum points/coverage, fixed angular masks, or fabricating endpoints from coarse candidate bounds were rejected. A free-form polynomial was rejected because it can fit shadow curvature and weakens the physical straight-wall model.

## R4 — Contrast-only source adjudication

**Decision**: Add source-adjudication v2. It may override only an exact original `edge_contrast_asymmetry` rejection when every original non-contrast check passes: gradient symmetry, normalized profile similarity/correlation, radial coverage and endpoint structure. It owns no new tunable numeric threshold and uses the original versioned checks unchanged.

**Rationale**: All 54 new 027 source failures are contrast-only while their normalized structural checks pass. `part-008` supplies a direct counterexample to classifying contrast asymmetry as occlusion: the groove is far from the fixture and sixteen d776-valid frames regressed. Preserving the original failed gate plus a separate effective decision is auditable and is not a silent relaxation.

**Alternatives considered**: Raising the contrast threshold, using only endpoint difference, or declaring every contrast-only failure mixed/occluded were rejected.

## R5 — Shadow semantics require overlap evidence

**Decision**: Version the source discriminator so `REAL_GROOVE_SHADOW_MIXED_OR_OCCLUDED` requires structural wall/source failure or explicit overlap/missing-wall evidence. Contrast-only rejection is classified as illumination asymmetry unless a separate image/geometric overlap check proves shadow mixing. `REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW` requires one effective survivor plus a nearby rejected dark-source candidate or external dark region whose geometry does not overlap either selected wall.

**Rationale**: The 027 classifier over-attributed all source failures to occlusion. Relative candidate/sidewall geometry is rotation invariant and does not need a fixed top-of-image whitelist.

**Alternatives considered**: Existing unverified fixture angle templates, filenames, sample IDs, target angle and manual truth at runtime were rejected.

## Decision 5: Treat the stationary two-body fixture as verified context, not an angle mask

**Decision**: Detect the upper-small/lower-large circular fixture bodies from closed arcs, relative radii, alignment, texture and gray-level separation from black background. Store only versioned normalized calibration evidence, then re-detect and uniquely match it in every frame. The lower-large body is only a false-candidate source because the housing and groove lie physically above it; it must never be called an occluder. Only the upper-small body may supply an occlusion/mixing-risk context. A groove near that body still requires an independent U-shaped contour: two wall families, a curved inner floor/endpoint structure and connection to the physical outer circle.

**Rationale**: The owner confirmed that both fixture bodies and camera are stationary, that only the upper-small body can block the groove, and that representative crops show textured circular surfaces measurably different from the black background. This explains why a broad polar dark interval may be a lower-fixture false source or an upper-fixture/groove mixture without conflating the two. Per-frame verification prevents a stale calibration from silently becoming a fixed-angle truth rule.

**Alternatives considered**: An empty-scene reference is unavailable. A hard-coded right-side sector, unconditional background subtraction, or automatic rejection inside the fixture corridor was rejected because each can delete a genuine groove and violates FR-007.

## R6 — Circle failures remain fail-closed unless unchanged gates pass

**Decision**: Do not relax or add a special fallback for the two `part-023` frames initially. Preserve their unique-family evidence and explicit final residual failure. Only accept an implementation change if it improves family assignment generically and the final original residual, coverage, center-shift and radius gates all pass.

**Rationale**: Their suspect residuals occur in ten sectors with retained coverage only 0.556, so the existing bounded sector refit correctly refuses them. A local exclusion would be false. The two frames are only about 0.13–0.17 px beyond the final P95 gate, but threshold proximity is not proof.

**Alternatives considered**: Raising residual P95 or excluded-sector capacity was rejected.

## R7 — Compatibility and performance

**Decision**: All new strategies are nested, strictly validated and default off. Enabled paths sample an image once, bound peaks per radial row and hypotheses per side, perform at most one authoritative fit per selected wall, and keep diagnostics summarized.

**Rationale**: The server P95 for the 027 replay was about 1.67 seconds algorithm time, leaving bounded headroom below 2.5 seconds. Existing configurations and external legacy modules must remain valid when recovery is omitted.

## R8 — Stop and acceptance conditions

**Decision**: Completion on 140 means every transition is explained, all reviewed complete grooves have one unique physical survivor, and any remaining failure is evidence-backed and safe. The later 700 replay uses frozen code/config only. Production accuracy and PLC remain blocked until a new physically separate labelled cohort passes.

**Rationale**: Forcing 140/140 valid would contradict fail-closed governance if any frame lacks adequate evidence.

## Specification traceability

| Decision | Requirements | Success criteria | Implementation and verification |
|---|---|---|---|
| R1 frozen observed evidence | FR-013, FR-016 | SC-001, SC-011 | Three approved manifests, SHA-joined results, seven-part report; never used as unseen acceptance |
| R2 provisional recognition | FR-003, FR-004, FR-008 | SC-005 | `groove_recognition.py`, adapter unique-survivor chain, zero/multiple-survivor integration tests |
| R3 wall families | FR-006, FR-007 | SC-006, SC-008 | `groove_refinement.py`, bounded deterministic family tests and same-adapter repeats |
| R4 source adjudication | FR-002, FR-005 | SC-004 | `source_consistency_adjudication.py`, exact contrast-only and structural-negative tests |
| R5 fixture roles and U contour | FR-009, FR-017, FR-018 | SC-002, SC-003, SC-012 | `groove_shadow_geometry.py`, rotation/order tests, upper/lower disposition overlays and reviewed rejection crops |
| R6 circle fail-closed | FR-010 | SC-007 | unchanged final circle gates; broad-sector residual rejection test and two-frame audit |
| R7 compatibility/performance | FR-011, FR-012, FR-014 | SC-009, SC-010 | default-off six-image comparison, focused tests, root schemas and warm repeats |
| R8 stop conditions | FR-015, FR-016 | SC-011 | no PLC/HMI or main integration; new physically separate acceptance remains required |
