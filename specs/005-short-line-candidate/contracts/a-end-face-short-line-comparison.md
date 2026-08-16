# Contract: `a-end-face-short-line-comparison/1`

- 一行 JSONL 对应一个 Manifest imageId；任务集在读图前与 baseline JSONL 完全匹配。
- 输入只记录相对路径、属性和 SHA-256，不嵌入图片字节。
- `features` 对 19/30 保存核心/候选逐图对照；`coreFeatureStatus` 同时保存
  19、30、46、M78、80、86，供无图汇总。
- 接受 baseline `a-end-face-result/2` 与 `/3`；若是 `/3`，仍以不可改写的核心字段为基线并重新运行指定候选。
- 技术失败 baseline 不运行候选，输出 `baseline_failed` 和结构化错误。
- 根机器合同为 `contracts/a-end-face-short-line-comparison.schema.json`。
