# 137 壳体 A 端面检测算法

本仓库只承载 A 端面检测，不包含其他视觉引导业务。

## 检测核心来源

`algorithms/end_face/core.py` 原样来自桌面算法包
`/home/ubuntu/disk/zzx/算法/算法.zip` 内的 `A端面/repeatability_evaluation.py`，
SHA-256 为 `f408631e03563ac80f392ea7558b786c2e2bef61670d1f206486f883b9ff8fbc`。
本仓库没有重写圆、边缘、配准或量测逻辑；新增代码仅提供独立调用、严格 JSON 契约和来源追溯。

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
  --output /tmp/a-end-face-result.json \
  --task-id inspection-001 \
  --strict
```

`--output -` 可将 JSON 输出到标准输出。默认 `--pixel-size 1` 保留像素单位；只有传入经确认的
物理单位/像素比例时，核心才会增加物理量字段。JSON 中的非有限检测值统一写为 `null`，不会输出
非标准 `NaN` 或 `Infinity`。

接口契约见 `contracts/a-end-face-result.schema.json`，Spec Kit 规格、方案和已完成任务见
`specs/003-a-end-face-cli/`。

## 数据边界

- 原图、参考图、LabelMe 大标注、RAR/ZIP 和运行输出不进入 Git。
- `data/manifests/` 只保存小体积相对路径清单和 SHA-256。
- 检测失败返回结构化失败 JSON；单项质量字段无效时 `result.valid=false`。
- 本 CLI 只输出 A 端面量测结果，不提供视觉引导、PLC 写入或质量 OK/NG 业务。
