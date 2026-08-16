# Contract: `a-end-face-short-line-candidate-config/1`

- v1 仅支持规范特征 `19`、`30`。
- 配置分别定义参考模板采样、粗到细三自由度搜索和多证据质量门禁。
- 数字必须有限；范围非负、步长正数、最小值不得大于最大值；未知字段被拒绝。
- 该配置不包含也不能覆盖核心 `lateralSearch=12` 或固定 `1.4×median` 规则。
- 根机器合同为 `contracts/a-end-face-short-line-candidate-config.schema.json`。
