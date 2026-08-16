# Quickstart: 单一真值与无标注重复性诊断

先分别运行检测batch和唯一真值单图验收。然后准备仓库外manifest：

```json
{
  "schemaVersion": "hole2-single-truth-study-manifest/1",
  "frames": [
    {
      "fileName": "frame-001.bmp",
      "population": "normal",
      "role": "development",
      "captureGroupId": "sample-a"
    }
  ]
}
```

运行离线研究：

```bash
uv run python tools/analyze_hole2_single_truth_study.py \
  --jsonl '/外置/development-results.jsonl' \
  --jsonl '/外置/diagnostic-results.jsonl' \
  --manifest '/外置/study-manifest.json' \
  --truth-report '/外置/truth-anchor/key-metrics.json' \
  --output '/外置/single-truth-study.json' \
  --minimum-group-frames 20
```

manifest和报告均必须位于Git工作树外。`staticRepeatability`给出同组有效帧的样本标准差、6σ、
range和MAD；它评价算法的静态波动，不是真实像素误差。没有工程门限时只报告
`EVALUATED/INCOMPLETE`，不输出PASS/FAIL。

Mac完整batch已经按采集顺序写入JSONL时，不需要手写2200条manifest。显式指定每组20帧及
原始batch group的用途：

```bash
uv run python tools/analyze_hole2_single_truth_study.py \
  --jsonl '/外置/full-regression/current-capture-results.jsonl' \
  --group-size 20 \
  --group-role 'normal=normal/evaluation' \
  --group-role 'defective=defective/observation' \
  --truth-report '/外置/truth-anchor/key-metrics.json' \
  --output '/外置/full-regression/static-repeatability.json' \
  --minimum-group-frames 20
```

该模式只按JSONL中每个原始group的记录顺序每20条分组，不从文件名推断；调用者必须确认JSONL
没有漏帧且顺序符合采集顺序。若存在漏帧或重排，应使用逐帧manifest模式。
