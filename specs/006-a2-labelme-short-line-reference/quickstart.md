# Quickstart: Mac A2 LabelMe Reference

1. Choose one representative A2 physical sample and keep all 20 frames together as `development`.
2. Open one frame in LabelMe. Add exactly two `line` shapes named `19` and `30`, following the existing annotation direction. Do not embed/copy the image into Git.
3. Validate and record the image-free catalog:

```bash
uv run python tools/inspect_short_line_labelme.py \
  --annotation "/external/A2/dev-sample/a2-short-lines.json" \
  --output "/external/A2/outputs/a2-short-lines-catalog.json"
```

Create the development Manifest from a directory containing exactly one `sampleId/position` tree with 20 images:

```bash
uv run python tools/make_manifest.py \
  --input "/external/A2/development" \
  --output "/external/A2/dev20-manifest.json" \
  --dataset-id "a2-labelme-dev20" \
  --task a_end_face \
  --expected-repeats 20 \
  --split development
```

4. Compare the frozen candidate on the complete 20-frame development manifest:

```bash
uv run python tools/compare_short_line_candidates.py compare \
  --manifest "/external/A2/dev20-manifest.json" \
  --data-root "/external/A2" \
  --annotation "/external/reference/sample_1_label.json" \
  --short-line-labelme-reference "/external/A2/dev-sample/a2-short-lines.json" \
  --results-jsonl "/external/A2/outputs/a2-v2-dev20/results.jsonl" \
  --candidate-config config/end_face_short_line_candidate.v1.json \
  --development-group \
  --output-dir "/external/A2/outputs/a2-labelme-dev20"
```

5. Freeze the LabelMe/config hashes, then run the same command with the all-held-out-sample manifest. Do not include the development sample in that validation manifest.
