# 137 壳体 A 端面检测算法

本仓库只承载 A 端面检测，不包含其他视觉引导业务。

## 检测核心来源

`algorithms/end_face/core.py` 原样来自桌面算法包
`/home/ubuntu/disk/zzx/算法/算法.zip` 内的 `A端面/repeatability_evaluation.py`，
SHA-256 为 `f408631e03563ac80f392ea7558b786c2e2bef61670d1f206486f883b9ff8fbc`。
本仓库没有重写圆、边缘、配准或量测逻辑；新增代码仅提供独立调用、质量分层、严格 JSON 契约、
批量评估和来源追溯。

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
  --output /tmp/a-end-face-result.json \
  --task-id inspection-001 \
  --strict
```

`--output -` 可将 JSON 输出到标准输出。默认 `--pixel-size 1` 保留像素单位；只有传入经确认的
物理单位/像素比例时，核心才会增加物理量字段。JSON 中的非有限检测值统一写为 `null`，不会输出
非标准 `NaN` 或 `Infinity`。

当前契约为 `a-end-face-result/2`，三个状态不得混用：

- `technicalStatus`：检测程序是否执行完成；
- `result.localization.valid`（同 `result.valid`）：端面中心、尺度、旋转和定位方法是否通过策略；
- `result.measurementCompleteness.allValid`：所有带核心质量状态的特征是否均有效。

每个 `featureQuality.<特征>.coreValid` 都直接来自不变核心，不会被适配层强行改有效。默认策略不把
19、30、46、M78、80、86 等特征测量失败当成端面定位失败；如现场确认某特征属于定位必要项，必须
在新版本策略的 `requiredFeatureLabels` 中显式加入。

接口契约见 `contracts/a-end-face-result.schema.json`，质量分层与批量评估的 Spec Kit 规格见
`specs/004-quality-policy-batch/`。

## 批量质量评估

批量工具先完整校验外置 Manifest，再复用同一参考模型逐图检测：

```bash
uv run python tools/evaluate_end_face_batch.py detect \
  --manifest /external/a2-manifest.json \
  --data-root /external/A2 \
  --annotation /external/sample_1_label.json \
  --quality-policy config/end_face_quality.example.json \
  --output-dir outputs/a2-evaluation
```

输出 `results.jsonl` 和 `quality-summary.json`。也可用 `summarize` 子命令只传逐图结果流，在无图片的
服务器上重算技术成功率、定位率、测量完整率、耗时和逐特征来源/原因分布。

## 数据边界

- 原图、参考图、LabelMe 大标注、RAR/ZIP 和运行输出不进入 Git。
- `data/manifests/` 只保存小体积相对路径清单和 SHA-256。
- 检测失败返回结构化失败 JSON；单项特征无效时保持该项 `coreValid=false`，但不默认否决定位。
- 本 CLI 只输出 A 端面量测结果，不提供视觉引导、PLC 写入或质量 OK/NG 业务。
