# Quickstart: 同源性二级裁决

## 安全默认

新配置默认`enabled=false`，不改现有输出：

仓库中的`config/source-consistency-adjudication.example.json`固定为`enabled=false`。配置完全不含该字段时，
运行时不会生成新诊断，历史行为不变。

## Git外实验配置

只在Git外副本中显式开启：

```bash
uv run python tools/prepare_source_consistency_adjudication_config.py \
  --base-config "$BASE_CONFIG" \
  --output "$EXTERNAL_DIR/adjudication-022.experimental.json"
```

该工具拒绝仓库内输出、非`single_real_groove`配置、未启用020同源性门、非v2槽壁精修或任何对原
`sidewall_source_consistency.max_contrast_normalized_difference=0.12`的改动。

## 聚焦测试

```bash
uv run --with jsonschema python -m unittest -v \
  tests.test_source_consistency_adjudication \
  tests.test_sidewall_source_consistency_candidate \
  tests.test_single_real_groove \
  tests.test_slot_pose_contract
```

## 真实回放

用现140张三折manifest、原始BMP与Git外实验配置运行现有批量CLI。输出必须保持Git外、不覆盖基线。汇总至少分开：

- part-008: override、有效图像姿态与原contrast证据。
- part-019: 20/20必须仍拒绝，不得有角度或修正量。
- 其他组: 按原失败阶段报告，不靠二级裁决越过圆、候选、遮挡或多解门。

```bash
uv run python tools/summarize_source_consistency_adjudication.py \
  --results "$OUTPUT_DIR"/fold-01.jsonl "$OUTPUT_DIR"/fold-02.jsonl "$OUTPUT_DIR"/fold-03.jsonl \
  --output "$OUTPUT_DIR/summary.json"
```

对145另用既有`evaluate_clean_groove_pose_truth.py`对同一image SHA评价；候选角对人工角应保持约`0.013368°`误差。147无外圆真值，不产生最终角准确率。

## 必看字段

1. 原`diagnostics.grooveSourceConsistency`：不能被改写。
2. `diagnostics.sidewallSourceConsistencyAdjudication.decision/effectiveStatus/checks/failedChecks`。
3. `result.detectionStatus/guidanceStatus/currentAngleDeg/imageFrameCorrectionDeg`。
4. `result.mechanicalCorrectionDeg/plcCommand`：始终null/blocked。

## 不可越过的发布门

- 服务器候选通过不等于可合main。
- Mac必须用同源原始BMP独立回放。
- part-019任一有效角即为发布阻塞。
- 145是单图精度证据，不是数据集准确率。
- main与PLC/HMI不在022授权范围内。
