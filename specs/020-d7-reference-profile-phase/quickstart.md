# Quickstart: D7参考剖面候选

## 定向测试

```bash
python -m unittest tests.test_d7_reference_profile -v
```

## 权威同图候选

```bash
python tools/diagnose_d7_reference_profile.py \
  --reference-annotation /external/reference/端面标注样品.json \
  --reference-image /external/reference/Pic_2026_08_12_214449_1.bmp \
  --target-image /external/reference/Pic_2026_08_12_214449_1.bmp \
  --output /external/output/d7-reference-self.json
```

## 581/582候选（不读取目标真值）

```bash
python tools/diagnose_d7_reference_profile.py \
  --reference-annotation /external/reference/端面标注样品.json \
  --reference-image /external/reference/Pic_2026_08_12_214449_1.bmp \
  --target-image /external/groups/normal-group-030/Pic_2026_08_12_215711_581.bmp \
  --output /external/output/d7-profile-581.json
```

若提供`--target-labelme`，工具只在检测完成后追加离线逐侧对照；该参数不得传入正式检测入口。

## 解释边界

- 无目标LabelMe：只报告候选和质量，不能宣称准确度。
- 有目标LabelMe：可报告D7-A/B逐侧误差、总长度误差，以及
  `formalEvidenceTruthComparison.sides.{A,B}`中的外峰/中点/内峰和人工相位。
- 无论哪种情况，本阶段都不覆盖正式D7。
