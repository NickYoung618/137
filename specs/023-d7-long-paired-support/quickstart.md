# Quickstart: D7长范围同语义直边支持

## 1. 定向单元测试

```bash
uv run --with jsonschema python -m unittest \
  tests.test_current_capture_registration \
  tests.test_current_capture_contract \
  tests.test_hole2_batch_report \
  tests.test_hole2_batch_review
```

重点检查：双侧连续延伸、单侧失败回退、跨间隙拒绝、冻结数值、LabelMe flags和v6 REVIEW隔离。

## 2. 权威单图验收

```bash
bash scripts/run_hole2_single_acceptance.sh \
  "$REFERENCE_ANNOTATION" \
  "$REFERENCE_IMAGE" \
  "$TARGET_IMAGE" \
  "$LATEST_TRUTH_JSON" \
  "$OUTPUT_DIR/truth"
```

`LATEST_TRUTH_JSON`只由离线evaluate读取。要求D7<=2px、Phi直径<=1px。

## 3. 代表帧与5组100帧

```bash
uv run python tools/batch_current_capture.py \
  --reference-annotation "$REFERENCE_ANNOTATION" \
  --reference-image "$REFERENCE_IMAGE" \
  --config config/current_capture_registration.v1.json \
  --group "normal-group-010=$GROUPS_ROOT/normal-group-010" \
  --group "normal-group-030=$GROUPS_ROOT/normal-group-030" \
  --group "normal-group-050=$GROUPS_ROOT/normal-group-050" \
  --group "normal-group-080=$GROUPS_ROOT/normal-group-080" \
  --group "normal-group-100=$GROUPS_ROOT/normal-group-100" \
  --workers 4 \
  --output-dir "$OUTPUT_DIR/batch"
```

必须逐帧比较022冻结JSONL：registration/D7/Phi状态不变，D7/Phi数值绝对差<=`1e-9px`。

## 4. 审核图

```bash
uv run python tools/render_hole2_batch_report.py \
  --jsonl "$OUTPUT_DIR/batch/current-capture-results.jsonl" \
  --image-root "$GROUPS_ROOT" \
  --output-dir "$OUTPUT_DIR/review" \
  --frame Pic_2026_08_12_214855_181.bmp \
  --frame Pic_2026_08_12_215711_581.bmp \
  --frame Pic_2026_08_12_215711_582.bmp \
  --frame Pic_2026_08_12_220308_981.bmp
```

预期：581/582不得跨越B侧证据中断；981双侧显示段增长；181继续紫色REVIEW/证据不可用。

## 5. 门禁

```bash
uv run --with jsonschema python -m unittest discover -s tests -p 'test_*.py'
uv run python -m compileall -q algorithms tools tests
.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks
git diff --check
```

提交前确认`algorithms/hole_2/main.py`、配置、Schema和Phi无差异，且Git变更无BMP、JSONL、PNG/JPEG或运行目录。
