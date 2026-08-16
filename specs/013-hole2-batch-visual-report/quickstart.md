# Quickstart: 孔2单批次可视报告

先进入Mac上的实际仓库并同步：

```bash
cd '/Mac上的实际路径/137壳体检测-孔2柱面和端面检测'
git pull --ff-only origin main
```

默认全量生成：

```bash
uv run python tools/render_hole2_batch_report.py \
  --jsonl '/外置/current-capture-results.jsonl' \
  --image-root '/外置/原图根目录' \
  --output-dir '/外置/hole2-batch-report'
```

仅生成无效帧并限制预览宽度：

```bash
uv run python tools/render_hole2_batch_report.py \
  --jsonl '/外置/current-capture-results.jsonl' \
  --image-root '/外置/原图根目录' \
  --output-dir '/外置/hole2-invalid-report' \
  --only-invalid \
  --max-preview-width 1280
```

指定帧与估计采集组大小：

```bash
uv run python tools/render_hole2_batch_report.py \
  --jsonl '/外置/current-capture-results.jsonl' \
  --image-root '/外置/原图根目录' \
  --output-dir '/外置/hole2-selected-report' \
  --frame 'Pic_2026_08_12_215431_500' \
  --frame 'Pic_2026_08_12_215725_620' \
  --images-per-product 20
```

`captureGroupEstimate`只是按文件尾号形成的采集序列估计，不是已确认物理零件数。工具不读取
目标真值、不换算mm，也不输出生产OK/NG。

输出目录包含`summary.json`、`summary.txt`、`index.csv`，以及每条选中记录的
`preview.jpg`和`prediction.labelme.json`。输出目录必须位于Git仓库外并且应为空。
