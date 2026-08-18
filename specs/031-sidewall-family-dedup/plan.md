# Implementation Plan: Sidewall Family Deduplication

**Branch**: `031-sidewall-family-dedup` | **Date**: 2026-08-19 | **Spec**: [spec.md](spec.md)

## Summary

Add an explicit v2 wall-source strategy after bounded line hypotheses are fitted and before the existing uniqueness decision. It groups hypotheses only when finite shared-span geometry proves a common source, then requires each eligible wall to align with its own housing-circle radius. Complete-link grouping prevents transitive over-merging, and each group retains one deterministically ranked observed hypothesis. A versioned v3 source adjudication preserves every original threshold/result and can release only photometric-magnitude asymmetry behind two radial walls, a complete curved floor, normalized-profile/endpoint consistency and verified fixture-source exclusion. Corrected `bad-0102` is an observed positive root-cause regression; corrected `bad-0015` is an observed fail-closed regression.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: NumPy 2.4.4, Pillow 12.2.0, bundled legacy end-face core

**Storage**: Git-tracked code/config/contracts/specs; corrected images and replay artifacts remain Git-external with SHA-256 identity

**Testing**: `unittest`, JSON Schema Draft 2020-12 validation, synthetic geometry boundaries, corrected two-case replay, frozen observed replay, repeatability and warm performance

**Target Platform**: Offline Linux server and portable Mac replay

**Project Type**: Algorithm library plus offline configuration/report tooling

**Performance Goals**: Reused-adapter warm P95 no more than 2.5 seconds per 5472×3648 image; no additional image load or image sampling pass

**Constraints**: Deterministic bounded work; default-off/v1 compatibility; no global gate relaxation; no filename/sample/fixed-angle/manual truth; no main merge, PLC/HMI change, sealed part-006 access, production claim or PLC authorization

**Scale/Scope**: At most 64 fitted wall hypotheses per side, bounded pairwise equivalence comparisons, two corrected observed cases, later 700-image observed regression, physically separate acceptance pending

## Constitution Check

- **I Specification first**: PASS. Stories, requirements and measurable criteria explicitly cover same-source recovery and distinct-source fail-closed behavior.
- **II Coordinate contract**: PASS. Geometry remains in the detected physical-circle image frame, x-right/y-down, pixel length and clockwise image angle; no mechanical mapping changes.
- **III Quality and safe failure**: PASS. Missing/nonfinite equivalence evidence never merges; all original downstream gates remain authoritative and invalid guidance stays null.
- **IV Provenance and reproducibility**: PASS. Both corrected cases are bound by task ID and SHA-256 and remain observed diagnostic data outside Git.
- **V Modular controlled integration**: PASS. An additive versioned refinement strategy and nested diagnostics preserve v1 and top-level result compatibility.

Post-design re-check: PASS. The contract bounds work and evidence, requires an observed representative, preserves fixture-source enforcement for v1/v2, and keeps independent acceptance pending.

## Project Structure

### Documentation (this feature)

```text
specs/031-sidewall-family-dedup/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── wall-source-family.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
algorithms/slot_pose/
├── groove_refinement.py
├── groove_shadow_geometry.py
├── source_consistency_adjudication.py
├── contract.py
└── legacy_adapter.py

contracts/
├── slot-pose-config.schema.json
└── groove-wall-source-family-diagnostic.schema.json

tools/
├── prepare_single_shot_initial_config.py
└── summarize_slot_pose_diagnostics.py

tests/
├── test_groove_refinement.py
├── test_slot_pose_contract.py
├── test_legacy_adapter.py
├── test_single_real_groove.py
├── test_single_shot_initial_profile.py
└── test_slot_pose_diagnostic_summary.py
```

**Structure Decision**: Extend the existing groove-refinement module because the defect is the physical identity of already fitted per-side wall hypotheses. The adapter remains responsible for enforcing the unchanged fixture/U-contour safety chain. No new image reader, model, service or PLC path is introduced.

## Design

1. Keep the v1 strategy byte-compatible.
2. In explicit v2, canonicalize every fitted hypothesis and assign a stable ID independent of input order.
3. For every bounded pair, form a common longitudinal coordinate frame, intersect their observed point ranges, and compute finite shared support, shared span, direction delta, signed start/mid/end separation, separation P95/max and outer endpoint angle/chord distance.
4. Mark equivalence only when every v2 gate passes. Missing or degenerate evidence means not equivalent.
5. Build physical families with deterministic complete-link agglomeration; never single-link chain hypotheses.
6. Choose an existing hypothesis per family by support, residual, coverage, endpoint, canonical line and candidate signature. Never average/refit the family.
7. Preserve a prior v1 unique representative byte-for-byte. Only after v1 fails to decide, exclude v2 representatives whose direction does not align with the fitted housing radius at their own endpoint, then run the existing uniqueness/support-margin decision without changing its thresholds; lack of radial evidence falls back to the prior fail-closed v1 outcome.
8. Emit bounded versioned membership/comparison/family/radial diagnostics and an explicit `wallFamilyRecoveryUsed` signal consumed by the adapter safety chain.
9. Treat coarse overlap with both fixture sectors as non-authoritative only after radial two-wall plus curved-floor U-contour proof.
10. Preserve original source-consistency evidence and use v3 adjudication only for photometric magnitude failures when every locked shape/profile/fixture check passes.
11. Materialize a new portable single-shot profile version; keep earlier profiles reproducible.

## Complexity Tracking

No Constitution violations require justification. Pair comparison is bounded `O(H² × S)` with `H <= 64` and finite observed points already held in memory; it performs no image resampling.
