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

## LabelMe 标注语义

现有 A 端面 `sample_1_label.json` 的标注与核心解释已经核对：

| 稳定尺寸名 | 原始 LabelMe 标注 | 图形 | 核心解释 |
| --- | --- | --- | --- |
| 100 | 损坏直径字形 + `100` | `linestrip`，30 点 | 最大圆，外圆定位锚及半径/直径 |
| 71 | 损坏直径字形 + `71` | `linestrip`，26 点 | 最小圆，内孔定位及半径/直径 |
| 86 / 80 / M78 | 圆弧点集 | `linestrip`，85/88/85 点 | 中间环半径/直径 |
| 46 | 两端点 | `line` | 从中心到外缘的径向长度及角度 |
| 20 | 两端点 | `line` | 线段长度及角度 |
| 19 / 30 | 两端点 | `line` | 短线位置、方向和长度；旧标注长度约 44.80/26.20 px |
| 字符区域 | 四点区域 | `polygon` | 区域包围框和面积；不是定位必要项 |

LabelMe 中 19/30 必须各使用一个两点 `line`，点落在真实边缘并保持既有起止方向。原文件中的损坏
单位/直径字形不作为稳定身份，适配层统一映射为 `19`、`30`、`100` 等 canonical feature。

Mac A2 可从一个物理样品、一个位置的完整 20 张中选一张代表图，手工建立域内 19/30 参考。先检查
标注；输出 catalog 只有坐标、尺寸和 SHA，不包含嵌入的 `imageData`：

```bash
uv run python tools/inspect_short_line_labelme.py \
  --annotation "/external/A2/development/sample_001/CORRECTED-a2-short-lines.json" \
  --output "/external/A2/outputs/corrected-a2-short-lines-catalog.json"
```

当前先前提供的 A2 端点标注已因未吸附到真实阶梯强边而撤销，并由共享加载器按文件 SHA-256
拒绝。它不得用于模板、调参、真值或验收；真实 19/30 比较等待新的人工复核 LabelMe。重命名或
移动撤销文件不会绕过门禁。

传入 `--short-line-labelme-reference` 后，候选局部模板来自该外置 A2 标注图；桌面核心仍使用原参考，
其 SHA、旧量测和 `coreValid` 均不改变。`main-housing-registration-v2` 还会先枚举圆形实例、独立选择
主壳体、稳健拟合圆心/尺度并用环形外观估计角度，再投影真实 19/30 标注做局部搜索。旧 core 端点
只保留在对照诊断中，不参与 v2 搜索中心。候选输出 provenance 会记录 `external_labelme` 以及标注/
图片 SHA-256。v2 缺少外置 19/30 标注时严格拒绝；v1 仍可显式选择以保持兼容。

接口契约见 `contracts/a-end-face-result.schema.json`，质量分层与批量评估的 Spec Kit 规格见
`specs/004-quality-policy-batch/`；主壳体配准增量规格见 `specs/007-main-housing-registration/`。

## 批量质量评估

批量工具先完整校验外置 Manifest，再复用同一参考模型逐图检测：

```bash
uv run python tools/evaluate_end_face_batch.py detect \
  --manifest /external/a2-manifest.json \
  --data-root /external/A2 \
  --annotation /external/sample_1_label.json \
  --quality-policy config/end_face_quality.example.json \
  --short-line-candidate-config config/end_face_short_line_candidate.v1.json \
  --short-line-labelme-reference /external/A2/development/sample_001/CORRECTED-a2-short-lines.json \
  --output-dir outputs/a2-evaluation
```

输出 `results.jsonl` 和 `quality-summary.json`。也可用 `summarize` 子命令只传逐图结果流，在无图片的
服务器上重算技术成功率、定位率、测量完整率、耗时和逐特征来源/原因分布。

## Mac 外置 A2 注册诊断与候选比较

在更正的 19/30 真值到位前，只运行无标注主壳体注册诊断：

```bash
uv run python tools/diagnose_main_housing_registration.py batch \
  --reference-image "$HOME/Desktop/壳体项目/137/a2-labelme-development-20/representative.bmp" \
  --manifest "$HOME/Desktop/壳体项目/137/a2-development-20-manifest.json" \
  --data-root "$HOME/Desktop/壳体项目/137/A2" \
  --candidate-config config/end_face_short_line_candidate.v2.json \
  --output-dir "$HOME/Desktop/壳体项目/137/outputs/a2-registration-v2-development-20"
```

输出只含主壳体假设、圆心/尺度/角度和门限诊断，不含候选恢复语义。以下候选比较命令仅在
`CORRECTED-a2-short-lines.json` 经人工强边核对及严格 inspect 后才可运行。

既有 v2 `results.jsonl` 可直接作为不可改写基线；工具会先完整验证 Manifest 图片属性/SHA-256 和
`imageId/taskId` 一一对应，再读取图片运行候选：

```bash
uv run python tools/compare_short_line_candidates.py compare \
  --manifest "$HOME/Desktop/壳体项目/137/a2-development-20-manifest.json" \
  --data-root "$HOME/Desktop/壳体项目/137/A2" \
  --annotation "/path/to/sample_1_label.json" \
  --results-jsonl "$HOME/Desktop/壳体项目/137/outputs/a2-v2-development-20/results.jsonl" \
  --candidate-config config/end_face_short_line_candidate.v2.json \
  --short-line-labelme-reference "$HOME/Desktop/壳体项目/137/A2/development/sample_001/CORRECTED-a2-short-lines.json" \
  --development-group \
  --output-dir "$HOME/Desktop/壳体项目/137/outputs/a2-main-housing-v2-development-20"
```

输出 `short-line-comparison.jsonl` 和 `short-line-summary.json`。无图重统计：

```bash
uv run python tools/compare_short_line_candidates.py summarize \
  --comparison-jsonl "$HOME/Desktop/壳体项目/137/outputs/a2-short-line-labelme-development-20/short-line-comparison.jsonl" \
  --output "$HOME/Desktop/壳体项目/137/outputs/a2-short-line-labelme-development-20/short-line-summary-recomputed.json"
```

开发时同一样品/位置的 20 张必须全部留在 development Manifest；冻结标注 SHA 和配置 SHA 后，使用
不含该物理样品的全样品 Manifest 做 validation/acceptance。不得把同一组 20 帧随机拆到两个集合。
单张外置代表图只可用于注册诊断，不能据此宣称短线恢复或 25 张改善。25 张候选验收必须等更正
标注到位，再用冻结后的 v2 配置、同一标注/图片 SHA 在 Mac 外置数据上完整运行。撤销与注册诊断
增量规格见 `specs/008-revoke-invalid-anchor/`。

## 数据边界

- 原图、参考图、LabelMe 大标注、RAR/ZIP 和运行输出不进入 Git。
- `data/manifests/` 只保存小体积相对路径清单和 SHA-256。
- 检测失败返回结构化失败 JSON；单项特征无效时保持该项 `coreValid=false`，但不默认否决定位。
- 本 CLI 只输出 A 端面量测结果，不提供视觉引导、PLC 写入或质量 OK/NG 业务。
