# Quickstart: 单真槽闭环旋转引导

## 1. Validate the repository configuration

```bash
python -m unittest discover -s tests -v
python -m json.tool configs/slot_pose.default.json >/dev/null
```

The production-like closed-loop mode is opt-in through `single-real-groove-pose-config/3`. Existing v1/v2 and legacy modes remain unchanged.

## 2. Run one image

```bash
python -m algorithms.slot_pose.main \
  --image /path/to/input.jpg \
  --config /path/to/closed-loop-v3-config.json \
  --out /path/to/result.json
```

Interpret the result in this order:

1. `detectionStatus` says whether the circle, unique real groove, and opening geometry were reliable.
2. `guidanceStatus` says whether the reliably detected groove needs an image-frame adjustment.
3. `imageFrameCorrectionDeg` gives the shortest signed image-frame change; positive is clockwise and negative is counterclockwise.
4. `plcExecutionStatus` says whether that image-frame value may be transformed into an actuator command. In this feature it remains blocked until the physical mapping is confirmed.

Do not treat `DETECTED_NEEDS_ADJUSTMENT` as a failed image.

## 3. Generate the external review package

```bash
python tools/run_slot_pose_batch.py \
  --manifest /path/to/external/manifest.json \
  --data-root /path/to/external/a2-jpegs \
  --config /path/to/closed-loop-v3-config.json \
  --output /path/to/external/results-v3.jsonl

python tools/render_slot_pose_review.py \
  --manifest /path/to/external/manifest.json \
  --results /path/to/external/results-v3.jsonl \
  --data-root /path/to/external/a2-jpegs \
  --output-dir /path/to/external/review-output

python tools/export_reference_anchored_diagnostics.py \
  --manifest /path/to/external/manifest.json \
  --results /path/to/external/results-v3.jsonl \
  --data-root /path/to/external/a2-jpegs \
  --manual-review /path/to/external/manual-review.json \
  --reference-comparison /path/to/external/same-image-comparison.json \
  --output-dir /path/to/external/auto-labelme-output
```

The output directory is intentionally outside Git and contains overlays, AUTO LabelMe diagnostics, CSV files, review JSON, and the contact sheet.

## 4. Evidence rules

- Keep original images, videos, archives, overlays, AUTO LabelMe files, and private absolute paths outside Git.
- The 25 JPEGs have no per-image angle truth. Report state counts and observed stability only.
- Only the single manually annotated sample may provide a development reference for itself.
- Static repeatability remains `NOT_EVALUATED` until the same physical sample, pose, and acquisition condition are explicitly grouped.
- PLC commands remain unavailable until the camera-to-actuator mapping is confirmed on site.
