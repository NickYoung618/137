# Quickstart: A 端面短线候选诊断与测量改进

所有图片、标注、Manifest 和运行 JSONL 保持在仓库外。以下 `<external>`、`<repo>` 和 `<output>`
需替换为本机真实绝对路径。

## 单图参考资产

```bash
cd <repo>
uv sync --frozen
uv run python algorithms/end_face/main.py \
  --annotation <external>/sample_1_label.json \
  --image <external>/sample_1_reference.bmp \
  --quality-policy config/end_face_quality.example.json \
  --short-line-candidate-config config/end_face_short_line_candidate.v1.json \
  --output <output>/reference-v3.json
```

检查 19/30：旧 `featureQuality.*.coreValid` 与旧 `measurements` 保持核心事实；新增
`shortLineCandidates` 显示 ROI/coreSearch、候选搜索、所有检查及独立 `candidateValid`。

## Mac A2 既有 v2 结果逐图比较

建议把含空格的桌面路径全部用双引号包围：

```bash
cd <repo>
uv run python tools/compare_short_line_candidates.py compare \
  --manifest "<external>/a2-manifest.json" \
  --data-root "<external>/A2" \
  --annotation "<external>/sample_1_label.json" \
  --results-jsonl "$HOME/Desktop/壳体项目137/outputs/a2-v2-first-25/results.jsonl" \
  --candidate-config config/end_face_short_line_candidate.v1.json \
  --output-dir "$HOME/Desktop/壳体项目137/outputs/a2-short-line-v1-first-25"
```

工具先全量验证 Manifest 图片属性/SHA-256 以及 imageId/taskId 一一匹配，再读取任何图片。输出目录含：

- `short-line-comparison.jsonl`：25 条逐图旧/新对照及完整诊断。
- `short-line-summary.json`：19/30 恢复/退化/持续失败和 46/M78/80/86 旧核心统计。

若 Mac 的实际桌面目录名是“壳体项目137 outputs”而非上述层级，只替换两个输出路径，不移动或复制图片。

## 无图重新汇总

```bash
cd <repo>
uv run python tools/compare_short_line_candidates.py summarize \
  --comparison-jsonl "$HOME/Desktop/壳体项目137/outputs/a2-short-line-v1-first-25/short-line-comparison.jsonl" \
  --output "$HOME/Desktop/壳体项目137/outputs/a2-short-line-v1-first-25/short-line-summary-recomputed.json"
```

重建汇总必须与首次 `short-line-summary.json` 的统计字段完全一致。

## 服务器门禁

```bash
cd <repo>
uv run python -m unittest discover -s tests -v
uv run --with jsonschema python -m unittest tests.test_end_face_schemas -v
sha256sum algorithms/end_face/core.py
git ls-files | rg '\.(bmp|tiff?|jpe?g|png|zip|rar|jsonl)$' || true
git ls-files -z | xargs -0 -r stat -c '%s %n' | awk '$1 > 5242880 { print; failed=1 } END { exit failed }'
```

服务器参考/合成通过只能证明候选合同、几何恢复和失败保护可执行；真实 A2 的 `recovered/regressed`
必须以 Mac 上同一 Manifest 的比较汇总为准。
