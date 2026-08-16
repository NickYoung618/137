# Quickstart: 唯一人工参考

下列命令中的参考JSON/BMP必须分别为冻结的`018e...`/`faf...`，并且保持Git外置。

## 单图检测

```bash
uv run python tools/run_current_capture.py \
  --reference-annotation '/external/reference/端面标注样品.json' \
  --reference-image '/external/reference/Pic_2026_08_12_214449_1.bmp' \
  --target-image '/external/target.bmp' \
  --config config/current_capture_registration.v1.json \
  --out '/external/output/algorithm-result.json'
```

## 单图离线验收

```bash
bash scripts/run_hole2_single_acceptance.sh \
  '/external/reference/端面标注样品.json' \
  '/external/reference/Pic_2026_08_12_214449_1.bmp' \
  '/external/target.bmp' \
  '/external/target-truth.json' \
  '/external/output/single-acceptance'
```

`target-truth.json`只由第二步离线evaluate读取。当目标就是权威参考自身时，报告显式
`templateSelfCheck=true`，这不是多样本泛化证据。

## Mac全量技术回归

```bash
bash scripts/run_hole2_full_regression.sh \
  '/external/reference/端面标注样品.json' \
  '/external/reference/Pic_2026_08_12_214449_1.bmp' \
  '/external/normal-2000' \
  '/external/defective-200' \
  '/external/output/hole2-authoritative-reference-regression' \
  4
```

normal与defective必须严格分组；批处理不接受目标标注，不输出mm或OK/NG。
