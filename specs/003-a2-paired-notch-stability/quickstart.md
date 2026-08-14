# Quickstart: A2双缺口稳定检测与Mac验收

## 1. 服务器全量测试

```bash
uv sync
uv run python -m unittest discover -s tests -v
```

## 2. 历史legacy扫角回归

```bash
uv run python tools/generate_synthetic_slot_pose.py \
  --output-dir "$TMPDIR/slot-pose-legacy" --angles=-175,-170,-165,0,165,170,175 --repeats 1 --seed 137
uv run python tools/run_slot_pose_batch.py \
  --manifest "$TMPDIR/slot-pose-legacy/manifest.json" \
  --data-root "$TMPDIR/slot-pose-legacy/synthetic" \
  --config "$TMPDIR/slot-pose-legacy/synthetic-config.json" \
  --output "$TMPDIR/slot-pose-legacy/results.jsonl"
```

## 3. paired合成真值回归

```bash
uv run python tools/generate_synthetic_paired_notches.py \
  --output-dir "$TMPDIR/slot-pose-paired" --seed 137
uv run python tools/run_slot_pose_batch.py \
  --manifest "$TMPDIR/slot-pose-paired/manifest.json" \
  --data-root "$TMPDIR/slot-pose-paired/images" \
  --config "$TMPDIR/slot-pose-paired/config.json" \
  --output "$TMPDIR/slot-pose-paired/results.jsonl"
```

预期：平移、缩放、亮度/噪声和±180°环绕正样本通过；缺一槽、多余暗区、配对歧义、
裁切和错误配置样本fail-closed。

## 4. Mac A2外置数据一键验收

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

## 5. 正式结论门禁

B-001目标实体、B-002数据/工位映射、B-003机械角契约、B-004质量阈值和B-005 PLC/上位机契约未关闭时，
报告可提供诊断统计，但所有正式引导角仍为空，不接入PLC。
