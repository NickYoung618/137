# Implementation Plan: Fixture-Shadow Root-Cause Recovery

**Branch**: `028-fixture-shadow-root-cause` | **Date**: 2026-08-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/028-fixture-shadow-root-cause/spec.md`

## Summary

Repair three independently observed causes without lowering locked global thresholds: admit only narrowly defined provisional recognition candidates into downstream proof, replace per-radius strongest-edge wall fitting with bounded multi-peak wall-family selection, and adjudicate contrast-only source rejection using all existing non-contrast structural gates. Keep 026 circle quality fail-closed unless the existing bounded sector process satisfies unchanged final gates. Version diagnostics and replay the frozen 140-image, seven-part observed cohort with explicit prior/new transitions.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: NumPy 2.4.4, Pillow 12.2.0, bundled legacy end-face core

**Storage**: Git-tracked code/config schemas/specs; raw images and replay artifacts remain Git-external with SHA-256 manifests

**Testing**: `unittest`, JSON Schema Draft 2020-12 validation, frozen real-image batch replay and generated overlays

**Target Platform**: Offline Linux server and Mac replay using the same committed Python implementation

**Project Type**: Algorithm library plus offline CLI tooling

**Performance Goals**: Reused-adapter warm P95 no more than 2.5 seconds per 5472×3648 image

**Constraints**: Single image load; bounded candidates/hypotheses; deterministic ordering; default-off compatibility; no filename/sample/angle truth; no main merge, PLC/HMI change, sealed part-006 access, production claim, or global gate relaxation

**Scale/Scope**: 140 frozen observed images in seven 20-frame physical groups; later 700-frame observed diagnostic replay; separate physical acceptance remains pending

## Constitution Check

- **I Specification first**: PASS. Spec contains prioritized stories, measurable criteria and traceable requirements.
- **II Coordinate contract**: PASS. All recovery geometry remains in the detected physical-circle image frame with x-right/y-down/clockwise conventions; no mechanical mapping is introduced.
- **III Quality and safe failure**: PASS. Recovery requires a unique evidence-complete survivor; missing, multiple, nonfinite or structural failures remain invalid with null guidance/PLC fields.
- **IV Provenance and reproducibility**: PASS. 140 and 700 are explicitly observed diagnostics with frozen hashes/config/code; artifacts stay outside Git.
- **V Modular controlled integration**: PASS. Additive default-off strategies extend current recognition/refinement/source interfaces and preserve old paths.

Post-design re-check: PASS. Contracts retain original evidence, version effective decisions, bound all hypothesis counts and keep external result schemas backward compatible through open diagnostics.

## Project Structure

### Documentation (this feature)

```text
specs/028-fixture-shadow-root-cause/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── runtime-recovery.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
algorithms/slot_pose/
├── contract.py
├── groove_recognition.py
├── groove_refinement.py
├── groove_resolution.py
├── groove_shadow_geometry.py
├── source_consistency_adjudication.py
├── groove_shadow_discrimination.py
├── physical_outer_circle.py
├── full_frame_circle_locator.py
└── legacy_adapter.py

contracts/
├── slot-pose-config.schema.json
├── groove-shadow-source-diagnostic.schema.json
└── source-consistency-adjudication.schema.json

tools/
├── run_slot_pose_batch.py
├── render_slot_pose_review.py
└── trace_groove_shadow_sources.py

tests/
├── test_groove_recognition.py
├── test_groove_refinement.py
├── test_source_consistency_adjudication.py
├── test_groove_shadow_discrimination.py
├── test_single_real_groove.py
├── test_slot_pose_contract.py
├── test_physical_outer_circle.py
└── test_trace_groove_shadow_sources.py
```

**Structure Decision**: Extend the existing modular algorithm and offline evidence tools. A dedicated
`groove_shadow_geometry.py` module derives bounded, rotation-relative overlap and continuity evidence
from the already loaded image and candidate geometry; the semantic discriminator consumes that
evidence instead of inferring shadow from contrast alone. No new service, model dependency or PLC
integration is introduced.

## Complexity Tracking

No Constitution violations require justification.
