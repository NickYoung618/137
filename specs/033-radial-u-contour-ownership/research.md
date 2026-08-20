# Research: Position-Independent Radial U-Contour Ownership

## Decision 1: The terminal blocker is unresolved fixture ownership, not duplicate candidates

**Decision**: Keep the existing bounded ambiguity resolver. Add a refined ownership proof for the complete candidate.

**Rationale**: In all fourteen two-candidate false rejections, the smaller candidate correctly fails wall/floor evidence. The larger candidate has accepted physical refinement and would be the sole survivor, but source adjudication rejects it because `fixture_source_exclusion_verified` is false. `normal:0254` has only one candidate and fails identically, proving candidate duplication is not the terminal cause.

**Alternatives considered**: Blindly merge nested candidates was rejected because nested angular intervals can describe different physical structures and it would not fix `normal:0254`. Selecting the wider or higher-scoring candidate was rejected because it is order/score based and unsafe.

## Decision 2: Use the groove's own radial U-contour geometry

**Decision**: Verify housing ownership only when both observed wall lines are sufficiently radial relative to their own outer-circle endpoints, using a physical envelope derived from measured opening half-width plus the unchanged intersection tolerance, and the complete floor plus locked normalized source checks pass.

**Rationale**: The fifteen reviewed complete-visible cases have maximum wall-to-radius deviation from 5.92° to 12.75° for openings with 11.63°-12.00° half-width. The only reviewed occluded case that passes every non-photometric source check has two tangential fixture-like walls at 51.60° and 53.71°. Other occluded cases already fail wall, floor, coverage, endpoint or normalized-profile evidence. The derived envelope rotates with the groove and is not tied to fixture position or sample identity.

**Alternatives considered**: A fixed inter-fixture gap was rejected as position-specific overfitting. A fixed new wall-angle threshold was rejected because it would be tuned to observed samples. Coarse overlap alone was rejected because it caused the bug. A new pixel classifier was rejected because existing physical geometry is sufficient and a model would add unneeded complexity.

## Decision 3: Add source adjudication v5 rather than alter locked gates

**Decision**: Preserve source measurements, thresholds and every version-4 complete-U/visible-boundary decision. Version 5 adds a separate schema `/4` route that accepts only raw contrast/gradient failures after radial physical ownership is verified and normalized profile, coverage and endpoint checks already pass.

**Rationale**: The issue is evidence interpretation, not an incorrect global threshold. Keeping original failures visible preserves auditability and compatibility.

**Alternatives considered**: Raising contrast/gradient thresholds was rejected because it could release occluded fixture edges. Mutating v4 was rejected because previous configs must remain reproducible. Replacing instead of extending v4 was rejected because it would re-reject previously verified complete-U cases without new negative evidence.

## Decision 4: Constant-size diagnostics and work

**Decision**: Record two wall alignments, measured opening half-width and one derived radial envelope; add no new image sampling pass.

**Rationale**: The required evidence already exists after refinement. Constant-size geometry keeps performance deterministic and diagnostics bounded.

**Alternatives considered**: Re-running refinement per ownership hypothesis and sampling another polar band were rejected as unnecessary and harmful to the latency gate.

## Decision 5: Observed regression is not acceptance

**Decision**: Require 15/15 reviewed complete-visible recovery and 67/67 reviewed occlusion rejection in observed replay, while retaining the separate-new-part gate for any accuracy claim.

**Rationale**: The 700 images have been reviewed and used for diagnosis. They can prove non-regression but no longer qualify as unseen acceptance.

**Alternatives considered**: Reporting 633/700 as production accuracy was rejected because the manifest lacks independent truth and physical part identities.
