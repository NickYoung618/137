# 137 壳体检测算法

本仓库承载 137 壳体 A 端面与孔2柱面/端面检测；两类算法保持独立入口、配置和规格。

## 检测核心来源

## 孔2交付状态

当前已完成数据无关工具链、配置模板和现有 `hole_2` 算法适配。尺寸7已按确认语义实现
双边界拟合，Φ12.2已提供半径和显式像素直径列。正式毫米标定、20张重复性验证和生产
OK/NG仍等待真实图片、图纸确认及验收数据。

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

逐帧输出只含主壳体假设、圆心/尺度/角度和门限诊断，不含候选恢复语义。批量
`registration-summary.json` 使用 `a-end-face-main-housing-registration-summary/2`：对所有注册有效帧
汇总圆心/半径（像素及按每帧尺寸归一化）、尺度、旋转置信度/裕量、实例选择裕量、边缘覆盖与圆拟合
残差；线性量提供 count/min/max/mean/median/p05/p95/MAD，角度使用跨 ±180° 连续的环形统计。统计
只用于观察漂移，不参与有效判定。以下候选比较命令仅在 `CORRECTED-a2-short-lines.json` 经人工强边
核对及严格 inspect 后才可运行。

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
撤销门禁见 `specs/008-revoke-invalid-anchor/`，注册稳定性统计见
`specs/009-registration-stability/`。

## 数据边界

- 原图、参考图、LabelMe 大标注、RAR/ZIP 和运行输出不进入 Git。
- `data/manifests/` 只保存小体积相对路径清单和 SHA-256。
- 检测失败返回结构化失败 JSON；单项特征无效时保持该项 `coreValid=false`，但不默认否决定位。
- 本 CLI 只输出 A 端面量测结果，不提供视觉引导、PLC 写入或质量 OK/NG 业务。

## 孔2数据无关工具链与现拍检测

项目研发原则见 [Constitution](.specify/memory/constitution.md)。本轮数据无关基础的规格、方案和
任务记录位于 [001-data-independent-foundation](specs/001-data-independent-foundation/spec.md)。

## 数据无关工具链

安装固定依赖并运行测试：

```bash
uv sync
uv run python -m unittest discover -s tests -v
```

为外置图片生成Manifest：

```bash
uv run python tools/make_manifest.py \
  --input /path/to/hole2-data \
  --output data/manifests/hole2-batch-001.json \
  --dataset-id hole2-batch-001 \
  --task hole_2 \
  --expected-repeats 20 \
  --reference-image /path/to/hole2-data/sample_1/pos_1/image_001.bmp
```

在服务器或Mac验证同一批原图：

```bash
uv run python tools/validate_dataset.py \
  --manifest data/manifests/hole2-batch-001.json \
  --data-root /path/to/hole2-data \
  --config config/hole2_inspection.example.json \
  --report outputs/hole2-batch-001/validation.json
```

从算法测量CSV计算静态/动态重复性：

```bash
uv run python tools/evaluate_repeatability.py \
  --measurements outputs/hole2-batch-001/measurements.csv \
  --config config/hole2_inspection.example.json \
  --output-dir outputs/hole2-batch-001/repeatability
```

使用现有权威参考资产进行一图冒烟：

```bash
bash scripts/smoke_reference.sh
```

数据目录详见 [data/README.md](data/README.md)，算法适配及资产指纹见
[algorithms/hole_2/README.md](algorithms/hole_2/README.md)。

## 现拍样品姿态注册与孔2尺寸检测

002 功能在旧孔2 v6 之外增加四个离散方向、主同心圆全局定位、六组圆/圆弧空间一致性、
稳健相似变换和版本化质量门限。有效姿态才会接入 v6 双边界检测；`Φ12.2` 由独立现拍圆弧
候选保护，`7` 的横向测量轴由旧参考中“尺寸线与 `Φ12.2` 相切”的几何关系重建。旧参考
坐标业务列与目标图坐标同时输出。

检测入口不接受现拍 LabelMe；负责人确认 JSON 只能在结果冻结后由独立验收入口读取。完整
服务器/Mac 命令、哈希校验和证据限制见
[002 quickstart](specs/002-current-capture-registration/quickstart.md)。

负责人确认单图的当前结果（只代表像素几何，不代表重复性、毫米精度或生产 OK/NG）：

- 注册方向 `270°`，6 个空间支持，覆盖率 `1.0`，注册有效。
- `7`：预测 `317.5631 px`，真值 `316.0000 px`；长度误差 `1.5631 px`，无序端点平均误差 `2.3096 px`。
- `Φ12.2`：预测直径 `539.1520 px`，真值拟合直径 `539.2892 px`；直径误差 `0.1372 px`，圆心误差 `0.5013 px`。
- 最终审计复跑总耗时 `10275.41 ms`；检测与验收结果留在仓库外，未提交原图、标注或结果 JSON。

检测结果现在显式输出目标↔参考正/逆变换与技术质量状态；注册或任一
特征失败时 CLI 返回非零且不保留伪造几何。验收报告会汇总方向、候选分数/拒绝
原因、变换、特征质量与真实误差。Mac `2000` 正常品 + `200` 坏品的外置分组
批量命令见 [002 quickstart](specs/002-current-capture-registration/quickstart.md)。

`Φ12.2` 使用受控两阶段半径搜索：主下限保持 `0.88`，只有主候选在
下界饱和时才以 `0.84` 下限恢复一次，并在质量字段中显式记录。尺寸7
的新切线双边界失败时，只允许回退到已通过原 v6 双边界质量状态的有限结果。

### 可变点数圆验收与 LabelMe 补圆

`Φ12.2` 验收不再要求固定77点。合法输入是 `shape_type=linestrip`、至少8个有限点，
并通过现有 `CIRCLE_RESIDUAL_PX`/`circular_residual` 圆拟合质量门；历史资产恰好77点
仅是数据事实。

仓库已有圆拟合能力，但此前没有“读取部分圆弧并写回完整 LabelMe 圆”的工具。现在可在
Git 外置目录运行：

```bash
uv run python tools/complete_labelme_circle.py \
  --annotation "$EXTERNAL_CIRCLE_DIR/partial-circle.json" \
  --image "$EXTERNAL_CIRCLE_DIR/source.bmp" \
  --config config/labelme_circle_completion.example.json \
  --completed "$EXTERNAL_CIRCLE_DIR/completed-circle.json" \
  --report "$EXTERNAL_CIRCLE_DIR/completion-report.json" \
  --preview "$EXTERNAL_CIRCLE_DIR/completion-preview.jpg"
```

工具复用 Kasa 初值、稳健筛点和几何圆拟合；要求可见弧覆盖至少 `120°`，按圆周长与源点
中位间距自动推导完整圆点数，并重复首点闭合。输出固定标记
`auto_completed=true`、`human_verified=false`，只能作为 LabelMe 人工复核底稿，不是人工真值。
