# LabelMe Physical Outer-Circle Truth Contract

物理外圆truth必须在原始BMP上人工创建，不得由待测算法生成或自动确认。LabelMe标注要求：

- 恰好一个`shape_type=circle`、`label=physical_outer_circle_truth`的圆；第一点为圆心，第二点为圆周点。
- 根级`flags.human_verified=true`且`flags.independent_from_algorithm=true`。
- 标注员与复核员必须为不同人员；二者身份和truth版本由导出命令记录。
- `imagePath`必须是受控图像根目录下的安全相对路径；输出记录原图与标注JSON的SHA-256。
- 算法叠加圆可以另开窗口参考，但不得复制为truth或替代人工调整。

导出示例：

```bash
python tools/build_labelme_circle_truth.py \
  --annotation "$LABELME_JSON" --image-root "$A2_BMP_ROOT" \
  --annotator operator-a --reviewer quality-b --truth-version a2-circle-v1 \
  --output "$CIRCLE_TRUTH_JSON"
```

两点圆属于人工审阅truth但不是计量标定。若质量门槛要求亚像素绝对精度，仍须追加多弧段标注协议、
像素标定和量具/标定件溯源；在此之前只用于比较算法版本和发现系统偏差。
