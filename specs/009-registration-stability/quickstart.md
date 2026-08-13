# Quickstart: Registration Stability Statistics

## Server verification

```bash
.venv/bin/python -m unittest tests.test_registration_diagnostic -v
.venv/bin/python -m compileall -q tools tests
```

The synthetic tests cover known linear distributions, `+179°/-179°` circular
wrap, one-frame output, all-invalid output, strict Schema validation, and the
absence of measurement/candidate-status fields.

## Mac external registration-only run

```bash
cd "$HOME/Desktop/壳体项目/137"

.venv/bin/python tools/diagnose_main_housing_registration.py batch \
  --reference-image "$HOME/Desktop/壳体项目/137/a2-labelme-development-20/representative.bmp" \
  --manifest "$HOME/Desktop/壳体项目/137/manifests/a2-first-25.json" \
  --data-root "$HOME/Desktop/壳体项目/A2-extracted" \
  --candidate-config config/end_face_short_line_candidate.v2.json \
  --output-dir "$HOME/Desktop/壳体项目/137/outputs/a2-registration-stability-first-25"
```

Expected external outputs:

- `registration-diagnostics.jsonl`: per-frame registration-only records
- `registration-summary.json`: v2 counts, failure reasons, provenance, and
  stability distributions

Keep both outputs and all images outside Git. The statistics describe
registration only. Do not interpret them as 19/30 measurement recovery.

## Deferred measurement evaluation

Short-line comparison remains blocked until a corrected 19/30 LabelMe
reference is manually verified. The withdrawn annotation fingerprint remains
rejected by the shared loader regardless of filename or location.
