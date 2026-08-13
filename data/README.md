# A 端面外置数据约定

原图、参考图、LabelMe 大标注和派生图不得提交 Git。推荐外置结构：

```text
<data-root>/
├── sample_1_label.json
├── sample_1_reference.bmp
└── sample_1/
    ├── pos_1/
    ├── pos_2/
    └── pos_3/
```

每个 Manifest 只保存相对路径、图像属性与 SHA-256；同一批数据在不同机器上通过独立
`--data-root` 解析。原图保持不可变，不缩放、不转码。运行输出写到已被 Git 忽略的 `outputs/`。

批量端面评估要求 Manifest 的 `task` 为 `a_end_face`。工具在检测前验证每张图的路径、格式、尺寸、
模式、字节数和 SHA-256；任一不一致都会停止，不会把图片复制到输出目录。逐图结果使用 JSONL，
可单独传到无图服务器重算汇总；JSONL 和汇总运行产物均不得提交 Git。

一个物理样品在同一位置的 20 张连续图是一个不可拆分的组。开发可使用一个完整组；最终验证必须
使用其他物理样品的完整组。`validate_dataset.py` 会拒绝同一 `sampleId` 同时出现在 development 与
validation/acceptance split 的 Manifest。

外置 A2 手工 LabelMe 参考至少包含 canonical `19`、`30` 各一个两点 `line`；其 `imagePath` 指向
同目录或绝对路径下的代表图。可用 `tools/inspect_short_line_labelme.py` 在检测前校验，不读取其
`imageData` 作为算法输入，也不会把图片复制进输出。
