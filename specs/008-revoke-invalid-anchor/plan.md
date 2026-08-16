# Implementation Plan: Revoke Invalid A2 Short-Line Anchor

**Branch**: `008-revoke-invalid-anchor` | **Date**: 2026-08-14 | **Spec**: [spec.md](spec.md)

## Summary

Add a path-independent denylist gate to the shared external-reference loader,
remove the revoked A2 anchor from tests and evidence, and refactor the main
housing registrar so reference-instance selection consumes only image-derived
circle hypotheses. Add a registration-only single/batch diagnostic CLI whose
strict JSON contains no candidate or recovery semantics. Real 19/30 evaluation
stays blocked until corrected truth arrives.

## Technical context

**Language/Version**: Python 3.12
**Primary Dependencies**: NumPy, Pillow, existing immutable core helpers
**Storage**: External images/manifests; external diagnostic JSON/JSONL outputs
**Testing**: Python `unittest`, jsonschema, synthetic raster fixtures
**Target Platform**: Linux server and macOS CLI
**Project Type**: Library plus standalone CLI tools
**Performance Goals**: One bounded downsample/component pass and radial/polar registration per target
**Constraints**: No OpenCV/SciPy; no revoked truth; no core or legacy-result changes; no tracked raw/large files
**Scale/Scope**: Reference revocation, registration-only diagnostics, two deferred short-line features

## Constitution check

- **I — Traceability**: PASS. Revocation, decontamination, implementation, and tests map to feature 008 tasks.
- **II — Immutable core**: PASS. `core.py` remains byte-identical; only core-external callers change.
- **III — Reproducibility**: PASS. Diagnostics record image/config fingerprints and finite JSON.
- **IV — Safe failure**: PASS. Revoked or ambiguous inputs fail before candidate evaluation.
- **V — Data minimization**: PASS. Images, private annotations, and generated streams remain external.

Post-design re-check: PASS. The revoked fingerprint appears only in the safety
denylist and revocation specification, never as acceptance evidence.

## Technical design

1. Compute the external annotation SHA before parsing and reject known revoked
   fingerprints in the shared loader used by every entry point.
2. Remove `reference_lines` from `MainHousingRegistrar`. Build the reference
   coordinate system from gated image-derived circle hypotheses; require the
   largest supported circle to exceed the next physical instance by a
   configured radius-margin ratio.
3. Keep target selection and rotation gates unchanged. The future candidate
   adapter may project corrected LabelMe endpoints only after registration.
4. Add a registration-only CLI with `single` and `batch` modes. It loads only a
   reference image, target image(s), and the versioned registration config; it
   verifies and serializes the immutable core SHA before registration.
5. Retract 007 anchor claims/tests/commands and replace all real-data commands
   with corrected-reference placeholders or registration-only execution.

## Project structure

```text
algorithms/end_face/
├── core.py                            # immutable
├── main_housing_registration.py       # annotation-independent reference/target registration
└── short_line_candidate.py            # revoked-reference gate and deferred projection
config/
└── end_face_short_line_candidate.v2.json
contracts/
├── a-end-face-main-housing-registration-diagnostic.schema.json
└── a-end-face-main-housing-registration-summary.schema.json
tools/
└── diagnose_main_housing_registration.py
tests/
├── test_main_housing_registration.py
├── test_registration_diagnostic.py
└── test_short_line_labelme_reference.py
specs/007-main-housing-registration/   # corrected historical scope/evidence
specs/008-revoke-invalid-anchor/       # this increment
```

**Structure decision**: Keep registration reusable in the algorithm package,
and place transport/manifest/serialization concerns in a standalone tool.

## Complexity tracking

No constitution violations.
