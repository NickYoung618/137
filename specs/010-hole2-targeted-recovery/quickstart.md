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

## 注册恢复字段

`registration.registrationRecoveryPass=stable_multi_support` 表示 primary 已明确失败为
`no_valid_candidate`，且扩展局部精配准窗后的多支持几何候选通过了全部原门。
`primaryFailureReason` 保留触发原因。`ambiguous_candidates` 不会触发该恢复。

`Φ12.2.recoveryPass` 可为 `expanded_radius`、`center_recenter`或
`robust_multicircle`。每个特征顶层都输出 `sourceDetector`、`recoveryPass`和
`quality`；`recoveryPass=null` 表示未触发恢复分支，是否有效始终以
`measurementValid` 和 `quality` 为准。

尺寸7的 `recoveryPass=multi_parallel_bands` 表示已执行多平行带聚合；
它不表示必然有效。恢复失败后只有原v6结果本身通过
`ok:dual_boundary_fit` 时才能回退，回退会记录
`recoveryPass=v6_original_quality`。

`geometryConsistency.ratioSource=old_reference_annotation_geometry`；该检查只诊断或
拒绝粗大错边，`outputAdjustmentApplied` 固定为 `false`。最终离群下降仍以
Mac 2200张外置复验为准。

## LabelMe 部分圆弧补全

输入、原图和全部输出必须位于 Git 工作树外：

```bash
uv run python tools/complete_labelme_circle.py \
  --annotation "$EXTERNAL_CIRCLE_DIR/partial-circle.json" \
  --image "$EXTERNAL_CIRCLE_DIR/source.bmp" \
  --config config/labelme_circle_completion.example.json \
  --completed "$EXTERNAL_CIRCLE_DIR/completed-circle.json" \
  --report "$EXTERNAL_CIRCLE_DIR/completion-report.json" \
  --preview "$EXTERNAL_CIRCLE_DIR/completion-preview.jpg"
```

默认输入标签为 `outer_circle_visible_arc`，输出为闭合 `outer_circle_contour`。源圆弧必须不少于8个有限点、通过现有 `25 px` 中位径向残差门并覆盖至少 `120°`。输出点数由圆周长和源点中位间距计算；`auto_completed=true`、`human_verified=false` 表示必须回到 LabelMe 人工确认。
