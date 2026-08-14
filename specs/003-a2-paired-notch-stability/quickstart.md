# Quickstart: A2多槽角色几何与Mac验收

## 1. 服务器全量测试

```bash
uv sync
uv run python -m unittest discover -s tests -v
```

## 2. 历史legacy扫角回归

```bash
uv run python tools/generate_synthetic_slot_pose.py \
  --output-dir "${TMPDIR:-/tmp}/slot-pose-legacy" --angles=-175,-170,-165,0,165,170,175 --repeats 1 --seed 137
uv run python tools/make_manifest.py \
  --input "${TMPDIR:-/tmp}/slot-pose-legacy/synthetic" \
  --output "${TMPDIR:-/tmp}/slot-pose-legacy/manifest.json" \
  --dataset-id legacy-smoke --task slot_pose --expected-repeats 1
uv run python tools/run_slot_pose_batch.py \
  --manifest "${TMPDIR:-/tmp}/slot-pose-legacy/manifest.json" \
  --data-root "${TMPDIR:-/tmp}/slot-pose-legacy/synthetic" \
  --config "${TMPDIR:-/tmp}/slot-pose-legacy/synthetic-config.json" \
  --output "${TMPDIR:-/tmp}/slot-pose-legacy/results.jsonl"
```

## 3. paired合成真值回归

```bash
uv run python tools/generate_synthetic_paired_notches.py \
  --output-dir "${TMPDIR:-/tmp}/slot-pose-paired" --seed 137
uv run python tools/run_slot_pose_batch.py \
  --manifest "${TMPDIR:-/tmp}/slot-pose-paired/manifest.json" \
  --data-root "${TMPDIR:-/tmp}/slot-pose-paired/images" \
  --config "${TMPDIR:-/tmp}/slot-pose-paired/config.json" \
  --output "${TMPDIR:-/tmp}/slot-pose-paired/results.jsonl"
```

预期：平移、缩放、亮度/噪声和±180°环绕正样本通过；缺一槽、多余暗区、配对歧义、
裁切和错误配置样本fail-closed。

## 4. Mac A2外置数据一键验收

在读取A2前，先以`multi_notch_roles`合成图验证通用角色分配（额外候选不导致失败，角色缺失/歧义必须失败）：

```bash
uv run python tools/generate_synthetic_multi_notches.py \
  --output-dir "${TMPDIR:-/tmp}/slot-pose-multi-role" --seed 137
```

先根据采集记录准备显式分组CSV，再执行：

```bash
uv run python tools/run_a2_acceptance.py \
  --normal-root "$A2_NORMAL_ROOT" \
  --bad-root "$A2_BAD_ROOT" \
  --grouping "$A2_GROUPING_CSV" \
  --truth "$A2_TRUTH_CSV" \
  --config "$A2_CONFIG" \
  --output-dir "$A2_REPORT_DIR"
```

该命令按顺序生成并验证Manifest、运行批处理、校验truth，然后分别生成`normal-report.json`和
`bad-report.json`。所有路径由命令行提供；原图、压缩包和派生大图不写入仓库。

将批处理结果生成人工核对包（必须指向仓库外目录）：

```bash
uv run python tools/render_slot_pose_review.py \
  --manifest "$A2_MANIFEST" --results "$A2_RESULTS_JSONL" \
  --data-root "$A2_DATA_ROOT" --output-dir "$A2_REVIEW_DIR"
```

输出含`review.json`、`candidates.csv`、`overlays/`和`contact-sheet.jpg`。其中角色组合只是现场勾选用假设，
`roleSuggestionsAreAuthoritative=false`固定表示它们不是业务真值。

## 5. 正式结论门禁

B-006图纸datum、B-007输出用途、B-008 A2特征映射及B-001至B-005未关闭时，
报告可提供诊断统计，但所有正式引导角仍为空，不接入PLC。
