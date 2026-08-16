# Implementation Plan: Registration Stability Statistics

**Branch**: `009-registration-stability` | **Date**: 2026-08-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/009-registration-stability/spec.md`

## Summary

Extend the annotation-independent registration batch summary with deterministic
linear and circular stability distributions. Aggregate only technically
successful, registration-valid records, normalize center/radius per target
image, retain per-metric observation counts, and emit explicit nulls when data
is unavailable. Version the summary contract to v2 while retaining v1 for
historical outputs. Statistics remain diagnostic and never feed registration
or candidate acceptance.

## Technical Context

**Language/Version**: Python 3.12, locked by `pyproject.toml`

**Primary Dependencies**: NumPy 2.4.4, Pillow 12.2.0, immutable A-end-face core helpers

**Storage**: External Manifest/images plus generated external JSON/JSONL

**Testing**: Python `unittest`; `jsonschema` in the explicit Schema gate

**Target Platform**: Linux server and macOS command line

**Project Type**: Python library plus standalone CLI tools

**Performance Goals**: One linear pass over already materialized registration records; no additional image decode or registration pass

**Constraints**: No revoked truth, no threshold changes, no non-finite JSON, no core/legacy edits, no raw/generated assets in Git

**Scale/Scope**: One registration summary, 12 linear metrics plus one circular metric, typical 20/25-frame batches

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I — Traceability**: PASS. Statistics, safe-empty behavior, v2 contract,
  external command, tests, and gates map to feature 009 requirements/tasks.
- **II — Immutable core**: PASS. Work is confined to the existing diagnostic
  tool, contracts, tests, and documentation.
- **III — Reproducibility**: PASS. Existing input/core/config/stream fingerprints
  are retained; formulas and percentile interpolation are fixed.
- **IV — Safe failure**: PASS. Non-finite/missing observations are excluded and
  represented by count zero/nulls; statistics cannot promote registration.
- **V — Data minimization**: PASS. Synthetic fixtures are generated in temporary
  directories; real images and all output streams remain external.

Post-design re-check: PASS. No exception or Constitution amendment is needed.

## Technical Design

1. Materialize the batch registration records already produced by the tool.
2. Select only `technicalStatus=succeeded` and `registration.valid=true` for
   stability extraction.
3. Extract transform center/scale/rotation and selected-hypothesis radius,
   edge coverage, circle residual, confidence, and ambiguity fields.
4. Normalize center by target width/height and radius by the smaller image
   dimension before aggregation.
5. Summarize finite linear observations with deterministic common and robust
   descriptive statistics. Summarize angle with circular statistics and signed
   shortest-path deviations.
6. Emit the v2 summary and validate its success, all-invalid, sparse, wrap, and
   forbidden-field behavior. Preserve the v1 schema for existing outputs.

## Project Structure

### Documentation (this feature)

```text
specs/009-registration-stability/
├── checklists/requirements.md
├── contracts/registration-summary-v2.schema.json
├── data-model.md
├── plan.md
├── quickstart.md
├── research.md
├── spec.md
└── tasks.md
```

### Source Code (repository root)

```text
tools/
└── diagnose_main_housing_registration.py
contracts/
├── a-end-face-main-housing-registration-summary.schema.json      # retained v1
└── a-end-face-main-housing-registration-summary-v2.schema.json   # new v2
tests/
└── test_registration_diagnostic.py
README.md
algorithms/end_face/core.py                                       # immutable
```

**Structure Decision**: Keep statistical extraction and CLI transport together
in the existing registration-only tool, expose pure summary helpers for unit
tests, and add a separate v2 Schema rather than rewriting historical v1.

## Complexity Tracking

No Constitution violations.
