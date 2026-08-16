# Implementation Plan: 孔2单批次可视报告

**Branch**: `main` | **Date**: 2026-08-15 | **Spec**: `spec.md`

## Technical context

- Python 3.11+，仅使用标准库、Pillow和项目已有依赖。
- 输入/图片/输出全部Git外置；仓库只保存源码、测试和SpecKit文档。
- 不修改`algorithms/hole_2/current_capture.py`、config、Schema或质量门。

## Implementation order

1. 先写CLI契约与合成batch记录测试，确认工具缺失时红灯。
2. 实现严格JSONL读取、group+文件名身份、外置路径和图片解析。
3. 实现缩小JPEG、原坐标LabelMe预测JSON及失败预览。
4. 实现按group的完整统计、index和`captureGroupEstimate`。
5. 用服务器9帧外置资产跑真实小样并人工看图。
6. 更新analyze，执行全套测试和静态/资产门禁后提交推送。

## Output layout

```text
external-output/
├── summary.json
├── summary.txt
├── index.csv
└── records/
    └── <group>/
        └── <image-stem>/
            ├── preview.jpg
            └── prediction.labelme.json
```

## Risk controls

- 失效记录不丢弃；默认逐条生成并以红色显示失败。
- 原始坐标与预览缩放分离，测试冻结LabelMe坐标不缩放。
- group隔离贯穿计数、路径和序列估计。
- 序列组只称estimate并带固定免责声明，不输出物理产品数。
