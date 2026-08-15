# Quickstart: Phi实线拟合圆与D7证据审核

先用唯一人工参考生成仓库外batch JSONL，再生成审核报告：

```bash
uv run python tools/render_hole2_batch_report.py \
  --jsonl '/external/run/current-capture-results.jsonl' \
  --image-root '/external/development-images' \
  --output-dir '/external/review-018' \
  --max-preview-width 1536
```

- 蓝色实线：Phi完整数学拟合圆，不代表整圈都检测到边缘；
- 绿色局部弧：本张图实际命中的外缘证据；
- 橙色A/B：尺寸7两条实际拟合边界；
- 青色dimension：两边界之间的公法线尺寸标注。

所有生成物必须位于Git工作树外。预测LabelMe不是人工真值，也不是完整零件轮廓。
