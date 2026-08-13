# Contract: `a-end-face-result/3`

- v2 的 `technicalStatus`、`result.valid == result.localization.valid`、`measurementCompleteness`、
  `featureQuality.coreValid` 和 `measurements` 语义保持不变。
- 成功结果新增 `result.shortLineCandidates`；键是原始核心标签，值同时包含旧 core 状态、独立候选状态、
  候选量测、逐图差异、诊断和状态迁移。
- `candidateValid` 不得覆盖 `coreValid`，候选量测不得写回 `result.measurements`。
- `algorithm.shortLineCandidate` 记录 candidateId、algorithmVersion 和 configSha256；禁用时为 `null`。
- 失败结果仍为 `result=null`，不得输出伪造候选。
- 根机器合同为 `contracts/a-end-face-result.schema.json`。
