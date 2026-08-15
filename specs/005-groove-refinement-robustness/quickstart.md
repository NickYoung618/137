# Quickstart: 005槽壁亚像素精修稳定性

## 1. TDD与契约门

```bash
uv run python -m unittest tests.test_groove_refinement -v
uv run --with jsonschema python -m unittest \
  tests.test_slot_pose_contract tests.test_single_real_groove -v
```

## 2. 建立Git外v2配置

从已核验的全画面配置复制一份Git外副本，仅将：

```json
"threshold_version": "groove-sidewall-subpixel-v2"
```

保留`max_line_residual_p95_px=2.0`，不得为了恢复3张而放宽。

## 3. 25张v1/v2成对批跑

```bash
uv run python tools/run_slot_pose_batch.py \
  --manifest "$A2_MANIFEST" --data-root "$A2_DATA_ROOT" \
  --config "$A2_V1_CONFIG" --output "$A2_RESULT_DIR/results-v1.jsonl"

uv run python tools/run_slot_pose_batch.py \
  --manifest "$A2_MANIFEST" --data-root "$A2_DATA_ROOT" \
  --config "$A2_V2_CONFIG" --output "$A2_RESULT_DIR/results-v2.jsonl"
```

## 4. 审阅内点/拒绝点

```bash
uv run python tools/render_slot_pose_review.py \
  --manifest "$A2_MANIFEST" --data-root "$A2_DATA_ROOT" \
  --results "$A2_RESULT_DIR/results-v2.jsonl" \
  --output-dir "$A2_RESULT_DIR/review-v2"

uv run python tools/summarize_slot_pose_diagnostics.py \
  --run "v1=$A2_RESULT_DIR/review-v1/review.json" \
  --run "v2=$A2_RESULT_DIR/review-v2/review.json" \
  --output "$A2_RESULT_DIR/v1-v2-summary.json"
```

必须逐图确认蓝色全部检测点中的绿/黄内点跟随两侧物理槽壁，红叉拒绝的是圆角/纹理，白线是最终槽壁；不能只看25/25。

## 5. truth和静态重复性

每张进入真实精度验收的图都必须在LabelMe中人工标注同图物理外圆和真实槽开放边界，
并由不同人复核。先在Git外为Manifest一图一模板：

```bash
uv run python tools/prepare_real_case_annotations.py \
  --manifest "$A2_MANIFEST" --data-root "$A2_DATA_ROOT" \
  --output-dir "$A2_ANNOTATION_DIR"
```

人工完成后更新`annotation-index.json`的标注哈希/状态/人员，然后严格成对评估：

```bash
uv run python tools/evaluate_annotated_real_cases.py \
  --manifest "$A2_MANIFEST" --results "$A2_RESULT_DIR/results-v2.jsonl" \
  --annotation-index "$A2_ANNOTATION_DIR/annotation-index.json" \
  --data-root "$A2_DATA_ROOT" --annotation-root "$A2_ANNOTATION_DIR" \
  --config "$A2_V2_CONFIG" --output-dir "$A2_RESULT_DIR/annotated-comparison" --strict
```

输出每图都并列人工/检测圆心、半径、槽角、象限、差值和叠加图。采集记录未显式确认
同样品/同工位/同条件，或组内未满足有效复核帧数时，静态重复性保持`NOT_EVALUATED`。
评价值是“检测角-同图人工角”的环形残差极差、标准差和绝对偏离P95，不跨未分组角度直接求极差。
