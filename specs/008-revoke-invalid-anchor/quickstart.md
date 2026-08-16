# Quickstart: Registration Development While 19/30 Truth Is Blocked

## Run synthetic and safety tests

```bash
.venv/bin/python -m unittest \
  tests.test_main_housing_registration \
  tests.test_short_line_labelme_reference \
  tests.test_registration_diagnostic -v
```

## Registration-only single image

```bash
.venv/bin/python tools/diagnose_main_housing_registration.py single \
  --reference-image '/external/A2/reference/representative.bmp' \
  --target-image '/external/A2/sample/frame-001.bmp' \
  --candidate-config config/end_face_short_line_candidate.v2.json \
  --output '/external/A2/outputs/registration-frame-001.json'
```

This command does not accept a LabelMe file and does not output 19/30 status.

## Registration-only Mac batch

```bash
.venv/bin/python tools/diagnose_main_housing_registration.py batch \
  --reference-image '/Users/daizekai/Desktop/壳体项目/137/a2-labelme-development-20/representative.bmp' \
  --manifest '/Users/daizekai/Desktop/壳体项目/137/manifests/a2-first-25.json' \
  --data-root '/Users/daizekai/Desktop/壳体项目/A2-extracted' \
  --candidate-config config/end_face_short_line_candidate.v2.json \
  --output-dir '/Users/daizekai/Desktop/壳体项目/137/outputs/a2-registration-only-first-25'
```

## Deferred corrected-reference comparison

Do not run short-line acceptance until `/external/A2/CORRECTED-short-lines.json`
exists and has been manually verified against the radial-gradient boundaries.
Then use the existing compare command with that corrected path. The revoked
annotation will be rejected regardless of filename or location.
