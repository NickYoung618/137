# 外置数据目录规范

原始图片不提交Git。推荐目录：

```text
<data-root>/
├── development/
│   └── sample_1/
│   ├── angle_neg_10/          # 每个机械真值角度建议20张
│   ├── angle_zero/
│   └── angle_pos_10/
└── validation/
    └── sample_2/
        └── angle_zero/
```

Mac真实数据源当前记录为`/Users/daizekai/Desktop/壳体项目/A2.rar`。它未同步到服务器；建议在Mac
外置盘解压为上述结构，或由只读流式解包工具逐张送入算法。RAR、原始图片和派生大图均不得提交Git。

Manifest中的`position`当前承载采集位置/角度组名称；机械真值角度、零位和方向信息应放入批次的
受控元数据或后续标注扩展中，不从文件名自动猜测。

- 原图保持无损，不缩放、不转JPEG。
- 同一角度组的20张用于静态重复性；同一样品不同角度/换位后的组均值用于动态分析。
- Manifest只保存相对路径、元数据和SHA-256；Mac和服务器用不同`--data-root`验证同一清单。
- `data/raw`、`data/derived`和`outputs`不进入Git。
- 标注使用`contracts/slot-pose-annotation.schema.json`，真值角必须来自分度盘/编码器/受控设定，
  不能把算法输出反填成真值。
- 按物理样品划分development/tuning/validation/acceptance；同一原图及其派生图只能出现在一个split。
