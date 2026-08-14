# Drawing Angle Truth CSV Contract

图纸夹角诊断真值与`angle-truth-csv.md`的机械纠偏真值是两份契约，不得共用一个无类型角字段。

Required columns:

```text
image_sha256,truth_valid,included_angle_deg,truth_source,datum_definition_id,
feature_mapping_id,sample,condition,repeat,split,dataset_class
```

Rules:

- `included_angle_deg`只表示datum与target的`[0,180]`最小夹角，不表示带符号机械纠偏。
- `datum_definition_id`必须指向经确认的单上槽射线、上下槽轴或其他图纸基准定义。
- `feature_mapping_id`必须指向经确认的A2图像候选到图纸角色映射。
- 上述任一ID未确认时可保留诊断数值，但验收状态必须为`NOT_EVALUATED`。
- `85°±5° (Z106)`在B-007关闭前只是图纸标注证据，不自动产生OK/NG。
- 需要机械引导时，必须另行使用`angle-truth-csv.md`及已确认的换算/坐标契约。
