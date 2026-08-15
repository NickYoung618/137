# Quickstart: 单人工样板无真值诊断

## 1. 导出Git外诊断

```bash
uv run python tools/export_reference_anchored_diagnostics.py \
  --manifest "$A2_MANIFEST" --results "$A2_RESULTS" --data-root "$A2_DATA_ROOT" \
  --manual-review "$MANUAL_REVIEW_JSON" --reference-comparison "$REFERENCE_COMPARISON_JSON" \
  --output-dir "$A2_REFERENCE_DIAGNOSTIC_DIR"

uv run python tools/render_slot_pose_review.py \
  --manifest "$A2_MANIFEST" --results "$A2_RESULTS" --data-root "$A2_DATA_ROOT" \
  --output-dir "$A2_REFERENCE_DIAGNOSTIC_DIR/review-auto"
```

## 2. 人工查看

先看`$A2_REFERENCE_DIAGNOSTIC_DIR/review-auto/contact-sheet.jpg`总览，再用LabelMe打开
`$A2_REFERENCE_DIAGNOSTIC_DIR/labelme-auto/*.json`逐图核对。`AUTO_`图形是算法结果，不是人工真值，
不得复制到truth目录后直接标记为人工审核。

## 3. 查看值

- `development-reference.json`: 唯一人工BMP的人工/自动对比。
- `diagnostic-index.json`: 每图检测值、象限、85度诊断、错误和参考观测差。
- `diagnostics.csv`: 便于筛选失败、象限和角度。

当前25图没有各自真值和可信静态分组，因此accuracy/static repeatability必须显示`NOT_EVALUATED`。
