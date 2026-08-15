# Quickstart: 004全画面壳体外圆唯一定位

## 1. 基线与聚焦测试

```bash
uv run python -m unittest tests.test_full_frame_circle_locator -v
uv run python -m unittest tests.test_physical_outer_circle tests.test_legacy_adapter tests.test_slot_pose_contract -v
uv run python -m unittest discover -s tests -v
```

显式Schema门：

```bash
uv run --with jsonschema python -m unittest \
  tests.test_slot_pose_contract \
  tests.test_slot_pose_cli \
  tests.test_single_real_groove -v
```

## 2. 外置配置

复制配置到Git外路径，在副本中：

- 设置`detector.diagnostic_mode=single_real_groove`；
- 删除`detector.face_search_roi_normalized`；
- 设置`detector.full_frame_circle_locator.enabled=true`；
- 保持锁定gyj源码、标注和参考图的内容哈希一致；
- 保持`production_plc_mapping_confirmed=false`。

不得把外置配置的Mac/服务器数据绝对路径提交Git。

## 3. 单图全画面诊断

```bash
uv run python algorithms/slot_pose/main.py \
  --image "$A2_IMAGE" \
  --config "$A2_FULL_FRAME_CONFIG" \
  --task-id full-frame-smoke \
  --out "$A2_RESULT_DIR/smoke.json"
```

期望：`diagnostics.circleLocalization`存在；非唯一时明确失败；无论是否测得图像角，PLC未确认时顶层正式角仍为空。

## 4. 为每个真实案例建立标注状态

先在Git外生成待标注索引和LabelMe模板；模板不含伪造truth：

```bash
uv run python tools/prepare_real_case_annotations.py \
  --manifest "$A2_MANIFEST" --data-root "$A2_DATA_ROOT" \
  --output-dir "$A2_ANNOTATION_ROOT"

export A2_ANNOTATION_INDEX="$A2_ANNOTATION_ROOT/annotation-index.json"
```

在LabelMe中逐图至少标注`physical_outer_circle_truth`（circle）或
`physical_outer_circle_visible_arc_manual`（linestrip），以及`target_groove_open_boundary_manual`开放槽边界；
补齐标注版本、标注员和不同的复核员，并将四个根级审核flags设成契约要求的值。重新运行准备命令刷新索引哈希后再做严格校验：

```bash
uv run python tools/evaluate_annotated_real_cases.py \
  --manifest "$A2_MANIFEST" --data-root "$A2_DATA_ROOT" \
  --annotation-root "$A2_ANNOTATION_ROOT" --annotation-index "$A2_ANNOTATION_INDEX" \
  --results "$A2_RESULT_DIR/full-frame.jsonl" \
  --config "$A2_FULL_FRAME_CONFIG" \
  --output-dir "$A2_RESULT_DIR/annotated-review" --strict
```

未标注、未复核或哈希不一致时，严格命令必须失败；比较值保持空，不填0。

## 5. 25张成对回放

先对同一Manifest分别运行全画面配置和冻结ROI配置：

```bash
uv run python tools/run_slot_pose_batch.py \
  --manifest "$A2_MANIFEST" --data-root "$A2_DATA_ROOT" \
  --config "$A2_FULL_FRAME_CONFIG" --output "$A2_RESULT_DIR/full-frame.jsonl"

uv run python tools/run_slot_pose_batch.py \
  --manifest "$A2_MANIFEST" --data-root "$A2_DATA_ROOT" \
  --config "$A2_ROI_CONFIG" --output "$A2_RESULT_DIR/roi.jsonl"
```

生成Git外审阅包：

```bash
uv run python tools/render_slot_pose_review.py \
  --manifest "$A2_MANIFEST" --data-root "$A2_DATA_ROOT" \
  --results "$A2_RESULT_DIR/full-frame.jsonl" \
  --output-dir "$A2_RESULT_DIR/review-full-frame"

uv run python tools/summarize_slot_pose_diagnostics.py \
  --run "full-frame=$A2_RESULT_DIR/review-full-frame/review.json" \
  --run "roi=$A2_RESULT_DIR/review-roi/review.json" \
  --output "$A2_RESULT_DIR/full-vs-roi-summary.json"
```

人工必须确认蓝色最终圆是壳体外圆，不能只看`status=accepted`。

## 6. 验收读取

至少核对：

- 全画面物理圆接受数和误选工装数；
- 候选数量、最佳/第二分数和歧义失败；
- 全画面与ROI圆心距离、半径差P95/max；
- 真实槽保留1个、阴影拒绝2个是否保持；
- 亚像素成功/失败分布；
- 定位阶段、完整单图P50/P95/max、墙钟吞吐、峰值RSS；
- 所有失败是否`valid=false`且正式角为空。
- 每个进入准确率统计的真实案例是否有人工作为参考；逐图是否同时显示人工值、自动值和差值。
- 静态重复性是否只按明确的同样品/同工位/同条件组，使用环形“检测角-人工角”残差统计；未确认分组时必须是`NOT_EVALUATED`。

JPEG结果只证明开发回归。角度精度验收必须回到外置原始BMP和独立人工truth。
