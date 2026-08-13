# 137 壳体 A 端面检测算法

本仓库只承载 A 端面检测，不包含其他视觉引导业务。

## 检测核心来源

`algorithms/end_face/core.py` 原样来自桌面算法包
`/home/ubuntu/disk/zzx/算法/算法.zip` 内的 `A端面/repeatability_evaluation.py`，
SHA-256 为 `f408631e03563ac80f392ea7558b786c2e2bef61670d1f206486f883b9ff8fbc`。
权威核心没有被改写；新增代码提供独立调用、质量分层、严格 JSON 契约、批量评估，以及核心之外的
19/30 参考梯度候选。候选有独立状态和失败保护，不会写回核心量测。

LabelMe 标注、参考图、待测原图和压缩包均为外置资产，不提交 Git。

## 安装与测试

```bash
uv sync
uv run python -m unittest discover -s tests -v
```

## 单图 CLI

标注中的 `imagePath` 必须能相对标注文件解析到外置参考图：

```bash
uv run python algorithms/end_face/main.py \
  --annotation /path/to/sample_1_label.json \
  --image /path/to/target.bmp \
  --quality-policy config/end_face_quality.example.json \
  --short-line-candidate-config config/end_face_short_line_candidate.v1.json \
  --output /tmp/a-end-face-result.json \
  --task-id inspection-001 \
  --strict
```

`--output -` 可将 JSON 输出到标准输出。默认 `--pixel-size 1` 保留像素单位；只有传入经确认的
物理单位/像素比例时，核心才会增加物理量字段。JSON 中的非有限检测值统一写为 `null`，不会输出
非标准 `NaN` 或 `Infinity`。

当前契约为 `a-end-face-result/3`，三个旧状态不得混用：

- `technicalStatus`：检测程序是否执行完成；
- `result.localization.valid`（同 `result.valid`）：端面中心、尺度、旋转和定位方法是否通过策略；
- `result.measurementCompleteness.allValid`：所有带核心质量状态的特征是否均有效。

每个 `featureQuality.<特征>.coreValid` 都直接来自不变核心，不会被适配层强行改有效。默认策略不把
19、30、46、M78、80、86 等特征测量失败当成端面定位失败；如现场确认某特征属于定位必要项，必须
在新版本策略的 `requiredFeatureLabels` 中显式加入。

v3 追加 `result.shortLineCandidates`：只为 19/30 保存核心基线、独立 `candidateValid`、候选几何、
ROI/对比度/梯度/峰值/搜索边界诊断、失败检查和 `recovered/regressed` 对照状态。候选采用二维参考
梯度联合配准，重新估计局部位置和方向；它不覆盖 `featureQuality`、`measurements`、定位状态或旧
`measurementCompleteness`。

接口契约见 `contracts/a-end-face-result.schema.json`，质量分层与批量评估的 Spec Kit 规格见
`specs/004-quality-policy-batch/`；短线候选增量规格见 `specs/005-short-line-candidate/`。

## 批量质量评估

批量工具先完整校验外置 Manifest，再复用同一参考模型逐图检测：

```bash
uv run python tools/evaluate_end_face_batch.py detect \
  --manifest /external/a2-manifest.json \
  --data-root /external/A2 \
  --annotation /external/sample_1_label.json \
  --quality-policy config/end_face_quality.example.json \
  --short-line-candidate-config config/end_face_short_line_candidate.v1.json \
  --output-dir outputs/a2-evaluation
```

输出 `results.jsonl` 和 `quality-summary.json`。也可用 `summarize` 子命令只传逐图结果流，在无图片的
服务器上重算技术成功率、定位率、测量完整率、耗时和逐特征来源/原因分布。

## Mac 外置 A2 逐图候选比较

既有 v2 `results.jsonl` 可直接作为不可改写基线；工具会先完整验证 Manifest 图片属性/SHA-256 和
`imageId/taskId` 一一对应，再读取图片运行候选：

```bash
uv run python tools/compare_short_line_candidates.py compare \
  --manifest "$HOME/Desktop/壳体项目/137/a2-manifest.json" \
  --data-root "$HOME/Desktop/壳体项目/137/A2" \
  --annotation "/path/to/sample_1_label.json" \
  --results-jsonl "$HOME/Desktop/壳体项目/137/outputs/a2-v2-first-25/results.jsonl" \
  --candidate-config config/end_face_short_line_candidate.v1.json \
  --output-dir "$HOME/Desktop/壳体项目/137/outputs/a2-short-line-v1-first-25"
```

输出 `short-line-comparison.jsonl` 和 `short-line-summary.json`。无图重统计：

```bash
uv run python tools/compare_short_line_candidates.py summarize \
  --comparison-jsonl "$HOME/Desktop/壳体项目/137/outputs/a2-short-line-v1-first-25/short-line-comparison.jsonl" \
  --output "$HOME/Desktop/壳体项目/137/outputs/a2-short-line-v1-first-25/short-line-summary-recomputed.json"
```

## 数据边界

- 原图、参考图、LabelMe 大标注、RAR/ZIP 和运行输出不进入 Git。
- `data/manifests/` 只保存小体积相对路径清单和 SHA-256。
- 检测失败返回结构化失败 JSON；单项特征无效时保持该项 `coreValid=false`，但不默认否决定位。
- 本 CLI 只输出 A 端面量测结果，不提供视觉引导、PLC 写入或质量 OK/NG 业务。
