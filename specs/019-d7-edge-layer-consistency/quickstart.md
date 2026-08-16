# Quickstart: D7边缘层一致性验证

## Unit tests

```bash
.venv/bin/python -m unittest tests.test_current_capture_registration
```

## External 030 group

```bash
.venv/bin/python tools/batch_current_capture.py \
  --reference-annotation "$REFERENCE_ANNOTATION" \
  --reference-image "$REFERENCE_IMAGE" \
  --config config/current_capture_registration.v1.json \
  --group "normal-group-030=$GROUP_030" \
  --workers 4 \
  --output-dir "$OUTPUT_DIR"
```

审核要点：

- 581仍为原paired-transition主路径且数值逐值不变。
- 582不再以单梯度multiband输出约317px。
- 如果582有效，必须有成对过渡层稳健拟合证据并通过所有原门；否则必须显式失败。
- 20张只报告路径分布和静态重复性，不宣称绝对准确度。

## Engineering gates

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python -m compileall algorithms tools tests
.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks
git diff --check
```

所有BMP、人工JSON、JSONL、预览和分析输出必须位于Git工作树外。
