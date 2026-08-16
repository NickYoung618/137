# 外置数据约定

## A 端面

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

Mac真实数据必须从命令行传入外置数据根，不在仓库文档、配置或代码中保存本机绝对路径。
建议在Mac外置盘解压为上述结构，或由只读流式解包工具逐张送入算法。RAR、原始图片和派生大图均不得提交Git。
每个 Manifest 只保存相对路径、图像属性与 SHA-256；同一批数据在不同机器上通过独立
`--data-root` 解析。原图保持不可变，不缩放、不转码。运行输出写到已被 Git 忽略的 `outputs/`。

批量端面评估要求 Manifest 的 `task` 为 `a_end_face`。工具在检测前验证每张图的路径、格式、尺寸、
模式、字节数和 SHA-256；任一不一致都会停止，不会把图片复制到输出目录。逐图结果使用 JSONL，
可单独传到无图服务器重算汇总；JSONL 和汇总运行产物均不得提交 Git。

- 原图保持无损，不缩放、不转JPEG。
- 同一角度组的20张用于静态重复性；同一样品不同角度/换位后的组均值用于动态分析。
- Manifest只保存相对路径、元数据和SHA-256；Mac和服务器用不同`--data-root`验证同一清单。
- `data/raw`、`data/derived`和`outputs`不进入Git。
- 标注使用`contracts/slot-pose-annotation.schema.json`，真值角必须来自分度盘/编码器/受控设定，
  不能把算法输出反填成真值。
- 按物理样品划分development/tuning/validation/acceptance；同一原图及其派生图只能出现在一个split。

## A2显式分组和truth

- 分组CSV列见`data/manifests/a2-grouping.example.csv`；`relative_path`相对于对应normal或bad数据根。
- `condition_id`必须来自采集记录、时间序列证据或人工受控映射，不按文件总数猜测。
- 角度truth列见`data/manifests/a2-angle-truth.example.csv`；正常图必须有外部真值来源和标定版本，
  坏图`truth_valid=false`且角度留空。
- 正常报告对环形误差/残差统计；跨不同真值组不对原始角均值求极差。坏图报告将任何
  `valid=true`计为误引导。失败样本不填0度。

一个物理样品在同一位置的 20 张连续图是一个不可拆分的组。开发可使用一个完整组；最终验证必须
使用其他物理样品的完整组。`validate_dataset.py` 会拒绝同一 `sampleId` 同时出现在 development 与
validation/acceptance split 的 Manifest。

外置 A2 手工 LabelMe 参考至少包含 canonical `19`、`30` 各一个两点 `line`；其 `imagePath` 指向
同目录或绝对路径下的代表图。可用 `tools/inspect_short_line_labelme.py` 在检测前校验，不读取其
`imageData` 作为算法输入，也不会把图片复制进输出。

## 孔2

原始图片不提交Git。推荐在服务器或Mac的外置数据根目录中使用：

```text
<data-root>/
├── sample_1/
│   ├── pos_1/                 # 固定位置重复采集，通常20张
│   │   ├── image_001.bmp
│   │   └── ...
│   └── pos_2/                 # 换位后重复采集，用于动态重复性
└── sample_2/
    └── pos_1/
```

约束：

- 原图保持无损，不缩放、不转JPEG；派生ROI必须与原图SHA-256和裁剪坐标关联。
- `sample_id + position + repeat_index`在一个Manifest内唯一。
- Manifest只保存相对路径；Mac和服务器通过不同的`--data-root`验证同一清单。
- 原图、派生图和运行输出分别放在`data/raw`、`data/derived`和`outputs`，均不进入Git。
- 可提交的内容仅包括`data/manifests/*.json`、配置、代码及小体积报告摘要。
