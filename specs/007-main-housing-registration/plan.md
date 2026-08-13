# Implementation Plan: Main Housing Registration for A2 Short Lines

**Branch**: `007-main-housing-registration` | **Date**: 2026-08-14 | **Spec**: [spec.md](spec.md)

## Summary

Add a versioned core-external v2 candidate. It discovers circular foreground
instances from a downsampled target, robustly fits each outer boundary, selects
the main housing against the external A2 reference model, estimates rotation
from annular appearance, and projects the manually labeled 19/30 lines before
the existing gated local gradient refinement. Legacy core output remains
read-only. Missing or ambiguous registration fails closed.

## Technical context

**Language/Version**: Python 3.12 (locked by `pyproject.toml`)  
**Primary Dependencies**: NumPy, Pillow; immutable desktop A-end-face core helpers  
**Storage**: External image/manifest files plus JSON/JSONL outputs  
**Testing**: Python `unittest`, jsonschema, synthetic raster fixtures, pinned external anchor smoke  
**Target Platform**: Linux server and macOS CLI  
**Project Type**: Library plus standalone CLI tools  
**Performance Goals**: Registration adds no more than one downsampled component pass and bounded radial/polar sampling per image  
**Constraints**: No OpenCV/SciPy dependency; no raw images/JSONL in Git; no old-transform search seed; no core edits  
**Scale/Scope**: Two candidate features, one external reference, 25-image Mac evaluation

## Constitution check

- **I — Spec traceability**: PASS. Requirements map to feature 007 tasks and tests.
- **II — Core reuse**: PASS. New logic is in a separate candidate module; core SHA is pinned and audited.
- **III — Reproducibility**: PASS. Candidate/config/reference hashes and registration diagnostics are serialized.
- **IV — Safe failure**: PASS. Registration gates fail closed and cannot mutate legacy quality or measurements.
- **V — Data minimization**: PASS. Anchor and A2 batches stay external; only tiny configs/specs/tests are tracked.

Post-design re-check: PASS. No constitution exception is required.

## Technical design

1. Build the reference housing model once from the external LabelMe image.
   Downsample, threshold, enumerate connected foreground components, and select
   the component whose robust outer circle contains both manual line anchors in
   the expected annulus.
2. On each target enumerate all plausible components, refine every component
   bbox circle with radial outer-boundary points, and score only candidates
   passing diameter, aspect, coverage, support, residual, and scale gates.
3. Compare each surviving instance's annular angular appearance with the
   reference. Select only when the best total score and its margin over the
   separated runner-up pass configuration.
4. Form a similarity transform from reference/target circle centers, scale,
   and angular shift. Project the external 19/30 endpoints.
5. Run the existing correlation/prominence/competing-peak local refinement
   around those projected endpoints. The old core target geometry is retained
   only under `core` and `deltaFromCore` diagnostics.

## Project structure

```text
algorithms/end_face/
├── main_housing_registration.py       # new instance selection and transform
├── short_line_candidate.py            # version dispatch and projected local search
└── core.py                            # immutable
config/
└── end_face_short_line_candidate.v2.json
contracts/
└── a-end-face-result-v3.schema.json   # permit v2 identifier/diagnostics
tests/
├── test_main_housing_registration.py
├── test_labelme_reference.py
└── test_short_line_candidate.py
specs/007-main-housing-registration/
├── contracts/registration-diagnostic.schema.json
├── data-model.md
├── plan.md
├── quickstart.md
├── research.md
├── spec.md
└── tasks.md
```

**Structure decision**: Extend the existing single Python package and CLI;
keep reusable registration independent of both the desktop core implementation
and batch transport code.

## Complexity tracking

No constitution violations.
