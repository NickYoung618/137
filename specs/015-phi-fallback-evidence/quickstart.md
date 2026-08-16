# Quickstart: Phi回退证据与累计圆心边界

```bash
uv run python -m unittest \
  tests.test_current_capture_registration \
  tests.test_current_capture_real_e2e -v

uv run python tools/batch_current_capture.py \
  --label '/外置/reference/annotation.json' \
  --reference-image '/外置/reference/reference.bmp' \
  --config config/current_capture_registration.v1.json \
  --group normal='/外置/normal-subset' \
  --output-dir '/外置/015-shadow' \
  --workers 4
```

重点审核`candidate_phase_inlier_fraction`、`candidate_global_center_*`与
`candidate_phase_fallback_rejection`。这些字段是图像证据，不是尺寸真值。

Mac全量回归后，确认JSONL按每个group的真实采集顺序写入且没有漏帧，再运行静态重复性：

```bash
uv run python tools/analyze_hole2_single_truth_study.py \
  --jsonl '/外置/full-regression/current-capture-results.jsonl' \
  --group-size 20 \
  --group-role 'normal=normal/evaluation' \
  --group-role 'defective=defective/observation' \
  --truth-report '/外置/single-truth/key-metrics.json' \
  --output '/外置/full-regression/static-repeatability.json' \
  --minimum-group-frames 20
```

若batch顺序不等于真实采集顺序或有漏帧，必须改用逐帧manifest，禁止按文件尾号猜组。
