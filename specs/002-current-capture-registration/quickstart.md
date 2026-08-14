# Quickstart: 现拍样品姿态注册与孔2尺寸检测

所有图片、现拍 LabelMe 和输出均保持外置。检测命令不接受现拍标注；只有第二步验收命令读取它。

## 1. 环境与回归测试

```bash
cd '/home/ubuntu/disk/dzk/137壳体检测-孔2柱面和端面检测'
uv sync --frozen
uv run python -m unittest discover -s tests -v
```

## 2. 单图检测（无现拍 JSON）

```bash
uv run python tools/run_current_capture.py \
  --label /path/to/old-hole2/annotation.json \
  --reference-image /path/to/old-hole2/reference.bmp \
  --target-image /path/to/current/Pic_2026_08_12_214449_1.bmp \
  --config config/current_capture_registration.v1.json \
  --out /path/to/external/outputs/current-capture-result.json
```

预期：输出评估四个正交方向，只有通过多组空间几何、残差和候选间隔门限的结果才将 `registration.registrationValid` 置为 true。运行时输入角色中不存在目标标注。

`Φ12.2` 先在半径比 `[0.88, 1.08]` 主区间搜索。仅当主结果命中 `0.88`
下界饱和时才以 `0.84` 下限重跑一次，并在
`features["Phi12.2"].quality.candidate_recovery_pass` 记录
`expanded_radius`。扩展结果仍须通过所有原质量门。

尺寸7新切线双边界失败时，只有 v6 原结果标记
`d7.quality.upstream=ok:dual_boundary_fit` 且五个几何值均有限才回退；
质量中记录 `candidate_fallback_pass=v6_original_quality`，`sourceDetector`
显式标识回退来源。

## 3. 外置真值离线验收

```bash
uv run python tools/evaluate_current_capture.py \
  --result /path/to/external/outputs/current-capture-result.json \
  --target-image /path/to/current/Pic_2026_08_12_214449_1.bmp \
  --target-annotation /path/to/current/Pic_2026_08_12_214449_1.json \
  --expected-image-sha256 faf357c2e6e8e58d667f76a3d9ed4f4d51ab4d451c2661cf0efbc641405b2d8b \
  --expected-annotation-sha256 f95e82c67c0d220fd8e34547b123723cc28a9ba67b4eddb9db2f5c1848f4dbc2 \
  --out /path/to/external/outputs/current-capture-acceptance.json
```

预期：严格接受且只接受 `7` 的两点 `line` 与 `Φ12.2` 的 77 点 `linestrip`，报告目标图像素误差。报告没有生产 PASS/FAIL，因为毫米标定、公差和重复性尚未确认。

验收报告的 `detectionSummary` 同时保留算法/配置版本、耗时、选择方向、正/逆
变换、所有候选分数/拒绝原因和两个特征的独立质量状态。`qualityStatus.state`
只是技术完整性，`productionDisposition` 始终为 `not_evaluated`。

## 4. 服务器/外置真实 E2E 回归

```bash
HOLE2_CURRENT_E2E_DIR=/path/to/confirmed-current-capture \
HOLE2_ASSET_DIR=/path/to/old-hole2 \
uv run python -m unittest tests.test_current_capture_real_e2e -v
```

资产存在时该测试必须先运行无真值检测，再运行 SHA 锁定的 LabelMe 验收；
资产不存在时显式 skip，不用合成图代替真实证据。
负责人确认单图的自动验收门为：尺寸7长度绝对误差 `≤2 px`，
`Φ12.2` 直径绝对误差 `≤1 px`。

## 5. Mac 2000 正常品 + 200 坏品外置批量回归

```bash
uv run python tools/batch_current_capture.py \
  --label '/path/to/old-hole2/annotation.json' \
  --reference-image '/path/to/old-hole2/reference.bmp' \
  --config config/current_capture_registration.v1.json \
  --group normal='/path/to/mac-data/normal-2000' \
  --group defective='/path/to/mac-data/defective-200' \
  --output-dir '/path/outside-repo/hole2-current-batch-20260814' \
  --workers 4
```

输出目录必须在 Git 工作树外。`current-capture-results.jsonl` 保留逐图完整候选和质量
证据，`quality-summary.json` 按 `normal`/`defective` 统计注册、两特征、方向、失败
原因和耗时。坏品不会被强制改为有效；该统计不输出产品 OK/NG。

## 6. Mac 单图外置复测

将仓库与旧参考资产路径替换为 Mac 实际位置，保持图片、标注与输出在仓库外。相同命令可处理另一张现拍图片；没有对应负责人确认真值时只执行第 2 步，不执行或伪造第 3 步。
