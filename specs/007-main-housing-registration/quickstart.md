# Quickstart: Main Housing Registration v2

Feature 008 withdrew the earlier A2 endpoint annotation. Do not run a
short-line acceptance comparison until a corrected LabelMe file has been
manually verified. Registration itself is annotation-independent.

## Run one registration diagnostic

```bash
.venv/bin/python tools/diagnose_main_housing_registration.py single \
  --reference-image /external/A2/reference/representative.bmp \
  --target-image /external/A2/targets/frame-001.bmp \
  --candidate-config config/end_face_short_line_candidate.v2.json \
  --output /external/A2/outputs/frame-001-registration.json
```

The JSON contains only reference/target provenance, housing hypotheses,
center/scale/angle registration and gates. It has no measurement or recovery
status.

## Run the external Mac Manifest

```bash
.venv/bin/python tools/diagnose_main_housing_registration.py batch \
  --reference-image "$HOME/Desktop/壳体项目/137/a2-labelme-development-20/representative.bmp" \
  --manifest "$HOME/Desktop/壳体项目/137/manifests/a2-first-25.json" \
  --data-root "$HOME/Desktop/壳体项目/A2-extracted" \
  --candidate-config config/end_face_short_line_candidate.v2.json \
  --output-dir "$HOME/Desktop/壳体项目/137/outputs/a2-registration-v2-first-25"
```

Images and generated JSON/JSONL remain outside Git.

## Deferred corrected-truth comparison

The existing comparison CLI remains fail-closed, but its
`--short-line-labelme-reference` argument must point to a future
`<CORRECTED_AND_MANUALLY_VERIFIED_A2_LABELME.json>`. Do not substitute old core
predictions or the withdrawn annotation. Only a complete Mac run may support a
25-frame short-line claim.
