# Quickstart: 负责人最小标注确认

在仓库外选择一张代表图，用LabelMe保留现有对象并追加：

1. `Phi12.2-outer-arc`：大圆外轮廓中负责人确认的那一侧可见弧，`linestrip`；只标这一侧；
2. 不补完整圆，不为了“对称”另造第二条弧；
3. `7-boundary-A`、`7-boundary-B`：窄颈两条真实平行直边，各用有限`line`或`linestrip`；
4. `7`：两条边之间的公法线尺寸连接线。

该证据级标注保持Git外置。它用于验证边缘对象和可视证据，不把图纸标称值作为算法输入。

## 服务器/本机生成可审计预览

先用现有批处理生成仓库外JSONL，再运行：

```bash
uv run python tools/render_hole2_batch_report.py \
  --jsonl '/external/run/current-capture-results.jsonl' \
  --image-root '/external/images' \
  --output-dir '/external/review-016' \
  --max-preview-width 1536
```

预览中绿色代表本张图实际接受的Phi局部弧；蓝色虚线完整圆是数学拟合模型，用于直观核对
拟合是否贴合外缘，不表示整圈均被检测。橙色两线是尺寸7的A/B物理
轮廓估计，青色线是独立垂距标注。LabelMe预测只包含：

- `prediction:Phi12.2:arc:reference_left:N` (`linestrip`；历史字段名，表示唯一校准弧)
- `prediction:Phi12.2:fit-circle` (`circle`；数学拟合模型，不是原始边缘证据)
- `prediction:7:boundary:A`、`:B`
- `prediction:7:dimension`

若校准弧证据不可用，工具不外推轮廓；数值有效性、证据完整性和失败原因分别保留。
预览顶部琥珀色表示“数值有效但证据不完整/不可审”，不是生产NG。输出目录
必须位于Git工作树外，且预测JSON不是人工真值或完整零件轮廓。

静态重复性必须由外置manifest明确给出同一样品/同一位置的重复帧，不能从文件名或“每20张”
自行推断：

```bash
uv run python tools/analyze_hole2_batch.py \
  --results-jsonl '/external/run/current-capture-results.jsonl' \
  --manifest '/external/repeatability-manifest.json' \
  --output '/external/run/repeatability-diagnostic.json'
```

重复性只说明同组结果的波动和缺测，不替代人工真值精度，也不能把不同零件混成一个静态组。
