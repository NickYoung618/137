# Quickstart: A 端面质量分层与批量评估

## 单图参考资产验证

标注、参考图和待测图均保持仓库外：

```bash
uv run python algorithms/end_face/main.py \
  --annotation /external/sample_1_label.json \
  --image /external/sample_1_reference.bmp \
  --quality-policy config/end_face_quality.example.json \
  --output /tmp/end-face-reference-v2.json
```

预期 `technicalStatus=succeeded`、`result.localization.valid=true`。参考图的 19、30 仍应在
`featureQuality` 中保持 `coreValid=false`，所以 `measurementCompleteness.allValid=false`。

## 外置数据 Manifest

```bash
uv run python tools/make_manifest.py \
  --input /external/A2 \
  --output /external/a2-manifest.json \
  --dataset-id a2-local-25 \
  --task a_end_face \
  --expected-repeats 25
```

Manifest 与结果证据可以同步；图片和 A2 归档不得同步或提交。

## 批量执行

```bash
uv run python tools/evaluate_end_face_batch.py detect \
  --manifest /external/a2-manifest.json \
  --data-root /external/A2 \
  --annotation /external/sample_1_label.json \
  --quality-policy config/end_face_quality.example.json \
  --output-dir outputs/a2-local-25
```

输出为 `results.jsonl` 和 `quality-summary.json`，目录默认被 Git 忽略。工具先验证全部图片属性和哈希，
验证失败时不会调用核心。

## 仅用结果证据重统计

```bash
uv run python tools/evaluate_end_face_batch.py summarize \
  --results-jsonl /external/results.jsonl \
  --output /external/quality-summary-recomputed.json
```

此模式不访问原图，适合从本机 A2 反馈向服务器传递脱图后的逐图结果证据。
