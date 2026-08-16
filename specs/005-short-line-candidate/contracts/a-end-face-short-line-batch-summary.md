# Contract: `a-end-face-short-line-batch-summary/1`

- 汇总只读取比较 JSONL，不访问图片、Manifest 或旧结果 JSONL。
- 19/30 分别报告 core/candidate 有效计数、四种迁移、失败检查分布和量测差异。
- 19、30、46、M78、80、86 分别报告旧 core 有效/无效、来源和原因分布。
- `acceptance.noRegression` 只在 19/30 的 `regressed` 总数为 0 时为真；
  `acceptance.hasEvidenceBackedRecovery` 只在 `recovered>0` 时为真。二者不改变任何逐图状态。
- 根机器合同为 `contracts/a-end-face-short-line-batch-summary.schema.json`。
