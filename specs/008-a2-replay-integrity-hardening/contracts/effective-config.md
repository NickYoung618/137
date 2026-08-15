# Effective Slot-Pose Configuration Contract v1

有效配置由`load_config`完整展开并严格校验。canonical identity包含：

```json
{
  "schemaVersion": "slot-pose-effective-config/1",
  "project": "137-housing-slot-pose",
  "pose": {},
  "detector": {},
  "legacyAssets": {
    "sourceSha256": "...",
    "annotationSha256": "...",
    "referenceSha256": "..."
  }
}
```

- 不包含config id、源文件格式和资产绝对路径。
- JSON必须拒绝NaN/Infinity，键排序、UTF-8、稳定分隔符。
- source SHA与effective SHA必须同时保留；二者语义不同。
- materialized config保留可运行字段并必须通过`slot-pose-config.schema.json`。
- v3 result的`algorithm.effectiveConfigSha256`为可选向后兼容字段。
