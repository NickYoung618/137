# Quickstart: 孔2定向恢复

## 离线诊断

重复组必须显式给出，不根据文件名猜测：

```bash
uv run python tools/analyze_hole2_batch.py \
  --results-jsonl /external/run/current-capture-results.jsonl \
  --group-size 20 \
  --ratio-baseline 0.585984 \
  --ratio-threshold 0.02 \
  --ratio-threshold 0.05 \
  --output /external/run/batch-diagnostics.json
```

或使用带 `sampleId/position` 的外置 Manifest：

```bash
uv run python tools/analyze_hole2_batch.py \
  --results-jsonl /external/run/current-capture-results.jsonl \
  --manifest /external/run/manifest.json \
  --output /external/run/batch-diagnostics.json
```

## Mac 2200 张全量回归

```bash
scripts/run_hole2_full_regression.sh \
  '/external/old-hole2/annotation.json' \
  '/external/old-hole2/reference.bmp' \
  '/external/data/normal-2000' \
  '/external/data/defective-200' \
  '/external/outputs/hole2-full-regression' \
  4
```

脚本保存 `full-regression.log`、`run-metadata.json`、`key-metrics.json`和
`key-metrics.txt`；它不接受目标标注。输出目录必须在 Git 工作树外。
