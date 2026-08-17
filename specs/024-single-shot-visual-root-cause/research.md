# Research

## Initial stage classification

- 141/161：`no_sparse_physical_candidate`，属于全画面圆候选至稀疏物理圆门。
- 441：`final_physical_circle/residual_p95`，属于最终物理圆质量门。
- 281：圆已通过，5个raw暗候选但0个真槽接受。
- 261：圆已通过，2个候选被接受，角色不唯一。
- 401：唯一槽候选通过，但`startSide_consensus_not_found`。
- 374：候选/精修形成混合边，现有同源性门正确拒绝。
- 145/147：当前成功对照，不得用于放宽门限。

## Decision

首轮不改算法。先生成审阅图并核对yyh/gyj，再决定每层是否有可验证修复；374固定为已知负例。

## Locked algorithm reuse audit

- The initial 024 audit found that runtime loaded the reviewed gyj A-end-face source by
  absolute asset path. That proved provenance but was not merge/deployment safe. The 024
  implementation now loads the single repository module `algorithms.end_face.core` in
  bundled mode, checks its byte SHA before use, and retains the reviewed upstream gyj SHA
  separately. The old external-file mode remains backward-compatible only.
- The inspected yyh production-integrated A-end-face source has the exact same SHA as
  the gyj source. There is therefore no second, different A-end-face circle algorithm
  to copy.
- The repository copy `algorithms/end_face/core.py` differs from the gyj source only in
  two CLI/reference default filenames; the circle fitting and outer radial-edge
  functions are identical.
- gyj/yyh hole-2 provides perpendicular one-dimensional edge sampling and robust line
  fitting. The slot implementation already uses the same subpixel profile principle and
  a stricter deterministic consensus TLS line selector with explicit ambiguity output.
  Replacing it wholesale would remove diagnostics and is not justified by current
  evidence.
- yyh hole-1 contains generic robust circle/line fitting. It does not contain fixture
  shadow versus square-groove semantics and is not a drop-in remedy for 281/261/401.

Conclusion: the currently proven circle primitives are already reused, not re-created,
and the mergeable path no longer imports source code from another repository.
The observed failures occur in slot-specific proposal/quality/semantic layers around
those primitives. Any next change must target a reproduced layer defect, while keeping
the locked gyj primitive and its source hash.

## Nine-case gate evidence

| Image | Stage | Observed gate evidence | Safe decision |
|---|---|---|---|
| 145 | success control | Valid, independently reviewed complete square groove | Keep as positive control; do not tune to it |
| 147 | success control | Valid, independently reviewed complete square groove | Keep as positive control; no pixel-level circle truth |
| 141 | sparse physical circle | Coarse seed `(2808,1832,r1640)` exists; sparse P95 `5.371px` exceeds scaled `5.316px`; 9 suspect sectors; robust refit rejected for too many sectors and retained coverage `0.694` | Physical edge identity is not yet proven; request an independent visible outer arc before changing gates |
| 161 | sparse physical circle | Coarse seed `(2808,1832,r1640)` exists; sparse P95 `5.955px` exceeds `5.316px`; 13 suspect sectors; retained coverage `0.583` | Same error code as 141 but materially broader inconsistency; do not treat as one threshold tweak |
| 441 | final physical circle | Sparse fit passes (`4.107px`); 720-ray final P95 becomes `5.654px`; 19 suspect sectors and only `0.417` retained coverage | The higher-resolution gate is exposing broad edge disagreement, not a near-boundary single-sector outlier |
| 281 | groove recognition | Physical circle passes; 5 raw dark regions, zero accepted. Candidate-002 passes all listed geometry checks except `width_variation_too_high`; the other 4 have no connected radial indentation | Need semantic confirmation that candidate-002 is the real groove before altering the width model |
| 261 | groove recognition | Physical circle passes; 6 raw regions; candidate-004 score `0.911` and candidate-006 score `0.852` both pass | Correctly fail-closed because two plausible openings remain; human must identify real groove versus fixture evidence |
| 401 | groove refinement | One candidate passes recognition; end wall has 27 support points, but start has 19 detected points and zero consensus support | Candidate region exists, but one straight-wall model is missing; human must state whether that wall is visible or occluded |
| 374 | source consistency | One true visible groove wall is human-confirmed; paired opposite edge is fixture shadow; source adjudication remains rejected (`endpointStructureDifference=0.0764 > 0.05`) | Known negative regression; must remain invalid |

These are gate-level causes, not yet physical ground truth for 141/161/441/281/261/401.
The first implementation pass therefore stops before threshold or detector changes.

## Minimum human review before a visual change

1. Circle group: on 141, 161 and 441, confirm which visible boundary is the physical
   housing outer edge. If a circle change is proposed, independently mark a sufficiently
   long visible arc on a development image and on a different-part validation image.
2. Candidate group: on 281, identify whether candidate-002 is the real square groove;
   on 261, identify which of candidate-004/candidate-006 is the real groove and whether
   the other is fixture shadow.
3. Refinement group: on 401, state whether both physical groove walls are visible. If
   both are visible, mark at least three independent points per wall plus both mouth
   endpoints; if one is hidden, record partial observation and keep failure closed.
4. No new review is required for 374: its mixed-wall negative semantics are already
   confirmed.
