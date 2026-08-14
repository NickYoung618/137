# Quickstart: 最新唯一真值重构

本文中的图片、LabelMe、运行 JSON 和诊断 PNG 都必须位于仓库外。完整命令在实现与门禁
完成后更新；检测步骤永远不接受目标标注，目标标注只进入后续离线诊断/验收步骤。

## 当前冻结资产

- target image SHA-256: `faf357c2e6e8e58d667f76a3d9ed4f4d51ab4d451c2661cf0efbc641405b2d8b`
- latest truth SHA-256: `018e3449c051c15f7946315bd0d7f21cd79f4d4983efca0d11c7d98f02bfffa6`

## 验收门

- 尺寸7目标图长度绝对误差 `<=2 px`
- `Phi12.2` 目标图直径绝对误差 `<=1 px`
- 旧审核 JSON 只输出历史对照，不阻断最新定义

## 外置基线边缘诊断

先用 `tools/run_current_capture.py` 生成不读取目标标注的结果，再执行：

```bash
uv run python tools/diagnose_latest_truth_edges.py \
  --result /external/output/algorithm-result.json \
  --reference-annotation /external/reference/annotation.json \
  --reference-image /external/reference/reference.bmp \
  --target-image /external/latest/Pic_2026_08_12_214449_1.bmp \
  --target-annotation /external/latest/端面标注样品.json \
  --expected-image-sha256 faf357c2e6e8e58d667f76a3d9ed4f4d51ab4d451c2661cf0efbc641405b2d8b \
  --expected-annotation-sha256 018e3449c051c15f7946315bd0d7f21cd79f4d4983efca0d11c7d98f02bfffa6 \
  --output-dir /external/output/edge-diagnostic
```

输出 `truth-prediction-overlay.png`、`d7-edge-profiles.json`、
`phi-radial-profile.json` 和 `diagnostic-summary.json`；输出目录在 Git 工作树内会被拒绝。

## 一键单图验收

```bash
bash scripts/run_hole2_single_acceptance.sh \
  /external/reference/annotation.json \
  /external/reference/reference.bmp \
  /external/latest/Pic_2026_08_12_214449_1.bmp \
  /external/latest/端面标注样品.json \
  /external/output/hole2-single-acceptance
```

脚本先运行不读取目标标注的检测，再执行离线验收，保存 `stdout.log`、`stderr.log`、
`exit-code.txt`、`run-metadata.json`、`algorithm-result.json`、
`acceptance-report.json`、`key-metrics.json` 和 `key-metrics.txt`。两个门同时通过时清楚打印
`PASS`；任何检测、验收或像素门失败都返回非零并打印 `FAIL` 或错误原因。

## Mac 2000正常 + 200坏品复测

```bash
bash scripts/run_hole2_full_regression.sh \
  /external/reference/annotation.json \
  /external/reference/reference.bmp \
  /external/mac/normal-2000 \
  /external/mac/defective-200 \
  /external/output/hole2-full-regression-v3 \
  4
```

最终接受条件：正常组 registration `>=1962`、尺寸7 `>=1863`、Phi `>=1922`，且按旧参考
比例计算的离群数不增加。服务器9帧只能证明控制帧500/521/620无新增失效，不能代替2200张结论。
