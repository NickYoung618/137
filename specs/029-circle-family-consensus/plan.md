# Implementation Plan: Circle-Family Consensus Stabilization

**Branch**: `029-circle-family-consensus` | **Date**: 2026-08-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/029-circle-family-consensus/spec.md`

## Summary

Add a version-2 corrective family-consolidation step after existing bounded circle hypotheses are grouped. A version-1 representative that already satisfies the unchanged authoritative residual gate is preserved exactly. Otherwise, version 2 derives a finite consensus only within that group, repeatedly reassigns one observed candidate per ray, refits, and requires stable assignments before the unchanged family and final physical-circle gates run. Version 1 remains byte-for-byte logical compatibility. Diagnostics expose the trigger decision and bounded consensus evidence, and frozen real-image replay verifies recovery without changing any circle threshold.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: NumPy 2.4.4, Pillow 12.2.0, bundled legacy end-face core

**Storage**: Git-tracked code, schema, tests and SpecKit artifacts; raw images/results remain Git-external with SHA-256 evidence

**Testing**: `unittest`, JSON Schema Draft 2020-12, frozen real-image batch replay, static repeatability and warm performance measurement

**Target Platform**: Linux server and Mac offline replay

**Project Type**: Algorithm library plus offline CLI tools

**Performance Goals**: Reused-adapter warm P95 no more than 2.5 seconds per 5472×3648 image

**Constraints**: One image load; bounded deterministic hypotheses and iterations; observed points only; candidate-order and rotation invariance; unchanged final gates; version-1 compatibility; no main merge, PLC/HMI change, sealed part-006 access or production claim

**Scale/Scope**: Focused synthetic tests, six-image 026 compatibility set, frozen 140-image observed cohort, later 700-image Mac diagnostic replay

## Constitution Check

- **I Specification first**: PASS. Three prioritized stories, FR/SC traceability and frozen-image acceptance conditions are explicit.
- **II Coordinate contract**: PASS. Consensus operates only in the existing image x-right/y-down pixel circle frame and does not change pose or mechanical conventions.
- **III Quality and safe failure**: PASS. Nonfinite, insufficient, non-convergent, zero-family and multi-family evidence fail explicitly; no final gate is relaxed.
- **IV Provenance and reproducibility**: PASS. Image/config/code hashes and observed-development status are required; artifacts remain outside Git.
- **V Modular controlled integration**: PASS. One strategy-versioned extension stays inside the existing circle-family module and preserves version 1.

Post-design re-check: PASS. The contract bounds iteration and diagnostics, retains observed points only, and keeps root result compatibility through additive open diagnostics.

## Project Structure

### Documentation (this feature)

```text
specs/029-circle-family-consensus/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── family-consensus.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
algorithms/slot_pose/
├── physical_outer_circle.py
├── full_frame_circle_locator.py
├── contract.py
└── legacy_adapter.py

contracts/
├── slot-pose-config.schema.json
└── physical-circle-edge-family-diagnostic.schema.json

tools/
├── prepare_single_shot_initial_config.py
└── trace_circle_edge_families.py

tests/
├── test_physical_outer_circle.py
├── test_full_frame_circle_locator.py
├── test_slot_pose_contract.py
├── test_circle_edge_family_trace.py
└── test_single_shot_initial_profile.py
```

**Structure Decision**: Extend the existing bounded selector in place behind a new strategy identifier. Do not add a second production implementation or alter the outer-circle primitive, robust fit, root result schema, PLC adapter or groove algorithms.

## Complexity Tracking

No Constitution violations require justification.
