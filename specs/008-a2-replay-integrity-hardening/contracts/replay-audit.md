# Replay Audit Contract v1

审计必须按 evaluation purpose 分区报告 `development`、`validation`、`test`、`acceptance`，并提供：

- 同一物理样品和源图 lineage 是否跨区；
- 每区人工真值数量及 `independentTruthStatus`；
- 锁定 acceptance 回放的运行原因、算法/有效配置身份；
- 当前只有一个人工标注样本时，validation/test 必须为 `NOT_AVAILABLE`，不得复用该样本补数。

700张已检查回放属于锁定 acceptance regression。实现期间只消费其现成 JSONL 做一次 release-candidate 审计，不反复运行检测图片，也不用于选择阈值。

输入：Manifest JSON + slot-pose result JSONL；不得读取原图或调用检测器。

输出Schema：`slot-pose-replay-audit/1`。

必须包含：

- 最终权威valid/detection/guidance/direction/error列联及一致性errors。
- 中间pre-quality状态，标记`authoritative=false`。
- dataset class和pose usability标签覆盖/来源。
- normal/bad及poseUsable分层stage funnel。
- conditional bad-directory metric和authoritative pose-usability metric分离。
- threshold observed/margin描述，`replacementThreshold=null`。
- repeatability eligibility；未显式分组时`NOT_EVALUATED`。
- annotation queue和BLOCKED项。
- audit自身wall时间及algorithm elapsed覆盖数。

严格门：Manifest/results数量、task/image hash映射、final状态语义或重复image id不一致时，audit状态为FAILED并返回非零CLI退出码。
