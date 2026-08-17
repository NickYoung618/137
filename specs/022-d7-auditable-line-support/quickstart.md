# Quickstart: D7可审核直边支持验证

## Environment

```bash
cd '/path/to/137壳体检测-孔2柱面和端面检测'
export REFERENCE_ANNOTATION='/external/reference/端面标注样品.json'
export REFERENCE_IMAGE='/external/reference/Pic_2026_08_12_214449_1.bmp'
export GENERALIZATION_ROOT='/external/hole2-generalization-100/groups'
export OUTPUT_ROOT='/external/output/hole2-d7-audit-022'
```

## Unit and contract tests

```bash
uv run --with jsonschema python -m unittest \
  tests.test_current_capture_registration \
  tests.test_current_capture_contract \
  tests.test_hole2_batch_report \
  tests.test_hole2_batch_review
```

## Five-group regression

```bash
uv run python tools/batch_current_capture.py \
  --reference-annotation "$REFERENCE_ANNOTATION" \
  --reference-image "$REFERENCE_IMAGE" \
  --config config/current_capture_registration.v1.json \
  --group "normal-group-010=$GENERALIZATION_ROOT/normal-group-010" \
  --group "normal-group-030=$GENERALIZATION_ROOT/normal-group-030" \
  --group "normal-group-050=$GENERALIZATION_ROOT/normal-group-050" \
  --group "normal-group-080=$GENERALIZATION_ROOT/normal-group-080" \
  --group "normal-group-100=$GENERALIZATION_ROOT/normal-group-100" \
  --workers 4 \
  --output-dir "$OUTPUT_ROOT/batch"
```

## Review output

```bash
uv run python tools/render_hole2_batch_report.py \
  --jsonl "$OUTPUT_ROOT/batch/current-capture-results.jsonl" \
  --image-root "$GENERALIZATION_ROOT" \
  --output-dir "$OUTPUT_ROOT/review" \
  --frame Pic_2026_08_12_214855_181.bmp \
  --frame Pic_2026_08_12_215711_581.bmp \
  --frame Pic_2026_08_12_215711_582.bmp \
  --frame Pic_2026_08_12_220308_981.bmp
```

检查正式橙色A/B只沿有paired支持的窄颈直段；左下D7 DETAIL应清楚显示A/B为直线。010紫色线必须
标为REVIEW，顶部仍显示证据不可用。短线表示同语义支持范围有限，不得据此手工拉长。

## Authority truth and gates

```bash
bash scripts/run_hole2_single_acceptance.sh \
  "$REFERENCE_ANNOTATION" "$REFERENCE_IMAGE" "$REFERENCE_IMAGE" \
  "$REFERENCE_ANNOTATION" "$OUTPUT_ROOT/truth"

uv run --with jsonschema python -m unittest discover -s tests -p 'test_*.py'
uv run python -m compileall algorithms tools tests
.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks
git diff --check
```

所有`$OUTPUT_ROOT`内容必须位于Git工作树外。
