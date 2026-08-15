# Drawing Angle Truth CSV Contract

图纸夹角诊断真值与`angle-truth-csv.md`的机械/PLC纠偏真值是两份契约，不得共用一个无类型角字段。

Required columns:

```text
image_sha256,truth_valid,included_angle_deg,truth_source,datum_definition_id,
feature_mapping_id,sample,condition,repeat,split,dataset_class
```

Rules:

- `included_angle_deg`只表示datum与target的`[0,180]`最小夹角，不表示带符号机械纠偏。
- 当前单真实槽v2的`datum_definition_id`固定指向“物理外圆圆心至图像向下+Y半轴”版本。
- 当前单真实槽v2的`feature_mapping_id`固定指向“唯一通过几何门的真实槽”版本；两个遮挡阴影不得映射。
- v2以顺时针有向角而非无向夹角判断：目标`+85°`、公差`±5°`，并要求槽口中点`dx<0,dy>=0`。
- v1或上述ID缺失时可保留绝对图像方位，但验收状态必须为`NOT_EVALUATED`。
- B-007已经关闭，v2可以产生`PASS|FAIL`；该状态仍不自动产生PLC可执行值。
- 需要机械引导时，必须另行使用`angle-truth-csv.md`及已确认的换算/坐标契约。
