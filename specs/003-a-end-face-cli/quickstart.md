# Quickstart: A 端面独立检测 CLI

> Historical v1 validation guide. Current quality semantics and CLI usage are defined in
> `specs/004-quality-policy-batch/quickstart.md`.

## Prerequisites

- Python 3.12 与 uv
- 外置 LabelMe 标注和其 `imagePath` 指向的参考图
- 一张外置 A 端面待测图

## Validate

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv run python algorithms/end_face/main.py \
  --annotation /path/to/sample_1_label.json \
  --image /path/to/target.bmp \
  --output /tmp/a-end-face-result.json
uv run python -m json.tool /tmp/a-end-face-result.json >/dev/null
```

成功结果遵循 [JSON Schema](contracts/a-end-face-result.schema.json)，包含 `technicalStatus=succeeded`、
量测对象和三个外置输入指纹。`result.valid=false` 表示核心至少报告一个无效质量特征，不等同于
命令执行失败。严格模式会对失败或无效结果返回退出码 1。
