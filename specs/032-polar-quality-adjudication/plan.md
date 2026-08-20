# Implementation Plan: Physical-Groove Polar Quality Adjudication

**Branch**: `codex/032-polar-quality-adjudication` | **Date**: 2026-08-20 | **Spec**: [spec.md](spec.md)

## Summary

Add a default-off, versioned decision after the single real groove has completed recognition, refinement and source/fixture verification but before the final quality failure is raised. The decision never changes the legacy polar score or threshold. It can remove only the sole effective `polar_score` terminal failure when one unique physical circle and one unique, fully proven U-contour groove already provide the image pose. Original and effective quality states remain separate and auditable.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: NumPy 2.4.4, Pillow 12.2.0, bundled legacy end-face core

**Storage**: Git-tracked code/config/contracts/specs; A2 images, reviews and replay results remain Git-external and SHA-identified

**Testing**: `unittest`, JSON Schema Draft 2020-12 validation, synthetic evidence fixtures, observed frozen replay, static repeatability and warm performance

**Target Platform**: Offline Linux server and portable Mac replay

**Project Type**: Algorithm library plus offline configuration/report tooling

**Performance Goals**: Reused-adapter warm P95 no more than 2.5 seconds per 5472×3648 frame; adjudication adds no image work and is bounded by a fixed set of diagnostic checks

**Constraints**: No threshold relaxation; original evidence immutable; default-off compatibility; one accepted circle and groove only; no filename/sample/fixed-angle/manual truth; no additional image decode/resampling/refinement; no main merge, PLC/HMI change, sealed part-006 access, production claim or PLC authorization

**Scale/Scope**: One constant-size decision per frame; 20-frame observed root-cause sequence, 24 recovered-valid and 174 mixed/occluded observed regressions; physically separate acceptance pending

## Constitution Check

- **I Specification first**: PASS. The sole-polar exception, physical proof chain, denial cases and measurable outcomes are explicitly specified.
- **II Coordinate contract**: PASS. Pose remains the refined physical-groove image angle in the detected-circle x-right/y-down clockwise frame; legacy polar rotation never supplies or biases pose.
- **III Quality and safe failure**: PASS. Original failure remains visible; any missing proof, ambiguity, mixed/occluded evidence or second failure denies adjudication and retains complete null safety.
- **IV Provenance and reproducibility**: PASS. Observed cases remain immutable Git-external diagnostics; new-part acceptance and human confirmation remain separate gates.
- **V Modular controlled integration**: PASS. A pure bounded decision module and optional nested config preserve prior behavior and avoid new image/model/hardware dependencies.

Post-design re-check: PASS. The contract separates original from effective quality, requires all current physical gates, adds no second analysis pass and keeps PLC non-authoritative.

## Project Structure

### Documentation (this feature)

```text
specs/032-polar-quality-adjudication/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── polar-quality-adjudication.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
algorithms/slot_pose/
├── polar_quality_adjudication.py
├── legacy_adapter.py
└── contract.py

contracts/
├── slot-pose-config.schema.json
└── polar-quality-adjudication-diagnostic.schema.json

tools/
├── prepare_single_shot_initial_config.py
└── summarize_slot_pose_diagnostics.py

tests/
├── test_polar_quality_adjudication.py
├── test_slot_pose_contract.py
├── test_legacy_adapter.py
├── test_single_real_groove.py
├── test_single_shot_initial_profile.py
└── test_slot_pose_diagnostic_summary.py
```

**Structure Decision**: Put evidence validation and the accept/deny state transition in one pure slot-pose module. The adapter supplies already computed diagnostics and owns effective failure propagation. No image function moves into the decision module, and the top-level result contract remains unchanged.

## Design

1. Preserve the original `quality.failedChecks` list before any decision and never mutate it.
2. Add strict default-off config `polar-quality-adjudication/1` paired with one supported strategy and development-only/non-PLC flags.
3. Validate a constant-size evidence bundle: sole polar failure; accepted circle and unique edge family; exactly one accepted recognition candidate; accepted single-groove pose/refinement; two observed walls and finite endpoints; accepted 5/5 curved floor; accepted effective source consistency; verified fixture-source exclusion; no fixed angle or runtime truth.
4. Return `NOT_NEEDED`, `ACCEPTED_OVERRIDE`, `REJECTED` or `NOT_EVALUATED` with original/effective failures and ordered checks. Invalid evidence fails closed.
5. In single-real-groove mode only, compute the decision after physical pose construction and before shadow-source classification. Use effective failures for classifier terminal status and final quality rejection; keep original failures in `quality` and add the independent adjudication diagnostic.
6. Confidence may retain the original polar score component; adjudication changes validity only and must not inflate confidence or substitute polar rotation for groove pose.
7. Keep omitted/disabled configs and all other diagnostic modes byte-logically compatible.
8. Materialize a new portable profile version and audit block without mutating v5 or prior artifacts.

## Complexity Tracking

No Constitution violations require justification.
