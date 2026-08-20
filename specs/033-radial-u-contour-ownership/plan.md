# Implementation Plan: Position-Independent Radial U-Contour Ownership

**Branch**: `codex/033-radial-u-contour-ownership` | **Date**: 2026-08-20 | **Spec**: [spec.md](spec.md)

## Summary

Add a default-off, rotation-independent ownership proof for a complete refined U-contour. It uses both observed wall directions relative to their own outer-circle radii, the measured opening half-width, the unchanged existing intersection tolerance, complete floor evidence and locked normalized source checks. A new source-adjudication version preserves prior version-4 complete-U/visible-boundary decisions and adds one stricter route that may ignore only raw contrast/gradient imbalance. Fixture location, fixed angles and the observed sample positions never enter the decision.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: NumPy 2.4.4, Pillow 12.2.0, bundled legacy end-face core

**Storage**: Git-tracked code/config/contracts/specs; A2 images and replay evidence remain Git-external and SHA-identified

**Testing**: `unittest`, JSON Schema Draft 2020-12, synthetic geometry fixtures, immutable observed replay, static repeatability and warm performance

**Target Platform**: Offline Linux server and portable Mac replay

**Project Type**: Algorithm library plus offline configuration/report tooling

**Performance Goals**: Reused-adapter warm P95 no more than 2.5 seconds per 5472×3648 frame; ownership work is constant-size over two endpoints and two fixture sectors

**Constraints**: Default-off; no threshold relaxation; original source evidence immutable; no file/sample/fixed-angle/manual truth; no extra image decode or full analysis pass; no main merge, PLC/HMI change, sealed part-006 access, production claim or PLC authorization

**Scale/Scope**: At most three existing coarse candidates and two refined walls/endpoints per candidate; 15 reviewed complete-visible and 67 reviewed mixed/occluded observed regression cases; synthetic full-rotation tests and physically separate acceptance pending

## Constitution Check

- **I Specification first**: PASS. Ownership, source-only adjudication, observed regression and new-part acceptance are separately specified and measurable.
- **II Coordinate contract**: PASS. Endpoint angles use the detected physical-circle x-right/y-down clockwise frame in degrees; pose computation is unchanged.
- **III Quality and safe failure**: PASS. Missing, same-body, mixed, incomplete, ambiguous and nonfinite evidence fail closed; original failures remain visible.
- **IV Provenance and reproducibility**: PASS. Observed A2 data stays immutable and external; configs, schemas and replay hashes are recorded.
- **V Modular controlled integration**: PASS. One bounded geometry proof extends existing fixture-source and source-adjudication modules with prior versions unchanged.

Post-design re-check: PASS. The design adds no implicit angle, threshold change, second analysis chain or PLC authority.

## Project Structure

### Documentation

```text
specs/033-radial-u-contour-ownership/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── radial-u-contour-ownership.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
algorithms/slot_pose/
├── groove_shadow_geometry.py
├── source_consistency_adjudication.py
├── legacy_adapter.py
└── contract.py

contracts/
├── slot-pose-config.schema.json
└── single-shot-initial-profile-v8.schema.json

tools/
├── prepare_single_shot_initial_config.py
└── summarize_slot_pose_diagnostics.py

tests/
├── test_groove_shadow_geometry.py
├── test_source_consistency_adjudication.py
├── test_single_real_groove.py
├── test_slot_pose_contract.py
├── test_single_shot_initial_profile.py
└── test_slot_pose_diagnostic_summary.py
```

**Structure Decision**: Extend the existing fixture geometry proof and source adjudicator rather than introduce another detector. The adapter already passes all required evidence and remains the only integration point.

## Design

1. Preserve current coarse overlap evidence unchanged.
2. Validate exactly two finite observed wall lines, their outer-circle endpoints, and a finite measured coarse opening half-width.
3. Reuse each wall's existing wall-to-radius alignment. Derive a position-independent admissible envelope from the measured opening half-width plus the unchanged `max_intersection_coarse_delta_deg`; do not introduce an observed-set angle threshold.
4. Verify radial U-contour ownership only when both walls fall inside that envelope, both walls and the observed floor are complete, and all locked normalized-profile, coverage and endpoint checks pass.
5. Emit `fixture-groove-source-exclusion/4` with both wall alignments, the derived envelope, ordered checks, original coarse overlap and `radialUContourOwnershipVerified`; otherwise retain prior schema behavior.
6. Add `source-consistency-adjudication/5`. It preserves every version-4 complete-U/visible-boundary decision, and its new schema `/4` radial-ownership route may accept only photometric-only failures. All old versions keep their exact behavior.
7. Materialize portable profile v8 and its audit schema without mutating v7.
8. In profile v8 only, disable the superseded development-only local-second-wall scan because v5 already emits the bounded ownership decision; keep the diagnostic available and unchanged in v7 and earlier.
9. Run synthetic full-rotation and fixture-edge counterexamples before focused, full, schema, 82-review regression, 700 observed replay, repeatability and warm performance checks. Treat observed results only as regression, never unseen accuracy.

## Complexity Tracking

No Constitution violations require justification.
