# Phase 0 Research: 真实槽与固定装置阴影源判别

## R1 — 证据包能证明什么

**Decision**: 将700张和207张失败行冻结为“已观察诊断组”，只用于建立失败阶段账本和开发回归；不从contact sheet推断逐图A/B人工真值。

**Rationale**: 上传包含索引、报告和按错误码拼接图，但不含原图、逐图运行JSON或逐图`REAL_GROOVE_*`人工标签。服务器另有同次700张完整结果JSONL，可按图像SHA联结，但Mac原图路径在服务器不可用。缺失的人工语义不能由错误码或缩略图替代。

**Alternatives rejected**:

- 把目录名“bad”当遮挡真值：目录不是物理或语义标签。
- 从contact sheet人工重标全部缩略图：分辨率不足且改变冻结证据口径。
- 把700张再次作为unseen acceptance：数据已观察，违反数据隔离。

## R2 — 判别证据来源

**Decision**: 不建立固定装置角度模板或新的阴影分数；复用现有`groove_recognition`、v2双壁`groove_refinement`、外圆肩部交点和原始`sidewall_source_consistency`门的结果。

**Rationale**: 这些证据直接回答两壁是否独立、连续、到达物理外圆肩部，以及两壁是否来自同类像素结构。它们是单图、旋转无关的物理证据，且已有锁定阈值和测试。Mac A2配置只启用了026外圆族，未启用候选ambiguity精修或source-consistency，因此46张ambiguity目前没有逐候选物理证据；这是“未评估”，不是新阈值失败。

**Alternatives rejected**:

- 固定屏蔽上方角区：固定角度泄漏且会拒绝真实槽。
- 按最高groove score或分差选候选：阴影候选可以获得相近分数，不能证明物理来源。
- 新增可调“shadow score”：会引入另一组未经独立冻结验证的阈值。
- 启用开发用source-consistency adjudication：该路径含门限性豁免，不符合本任务“不放宽source-consistency”。

## R3 — 三态裁决状态机

**Decision**: 运行时裁决只消费结构化候选证据：

- `REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW`: 恰好一个候选通过既有recognition、v2 refinement和原始source-consistency；至少一个竞争候选存在且每个竞争候选均有明确物理失败；上游外圆与全局质量门通过。
- `REAL_GROOVE_SHADOW_MIXED_OR_OCCLUDED`: 没有完整候选，且最可信的真槽候选有明确的壁、端点/外圆交点或source-consistency混合/缺失证据；仍然fail-closed。
- `INDETERMINATE`: 多个物理候选存活、证据未运行/缺失/非有限、容量溢出、上游或全局门失败，或无法安全区分混合与其他弱证据。

分类名称是诊断结论，不把被拒候选武断命名为固定装置；每个竞争候选另记录中性的`NON_GROOVE_SOURCE_REJECTED`及具体失败门。

**Rationale**: “唯一存活”沿用既有ambiguity resolver语义；竞争者必须有明确失败证据可避免用候选顺序或分数强选；证据不足单独保留避免过度归因。

**Alternatives rejected**:

- 只要一个候选通过就选：未评估竞争者仍可能是真槽或危险阴影混合。
- 将所有refinement失败都称为混合/遮挡：也可能是模糊、外圆误差或低对比度，必须保留`INDETERMINATE`。

## R4 — 与原决策链的关系

**Decision**: 新模块不能覆盖任何既有失败。`polar_score`、外圆、recognition、refinement、source-consistency和ambiguity保持原错误优先级；裁决仅在所需证据存在时附加诊断，并把`poseChainAllowed`约束为既有链允许且来源裁决允许。

**Rationale**: 当前`polar_score`在流程后段触发，因此即使局部证据完整也必须保持`QUALITY_REJECTED`。外圆不唯一时槽几何没有可靠坐标基准，不得生成语义分类。所有失败继续交由统一结果构建器清空角度、方向、修正与PLC字段。

## R5 — 配置与兼容

**Decision**: 增加`detector.groove_shadow_source_discrimination`严格对象，唯一行为开关默认`false`，版本`groove-shadow-source-discrimination/1`；不在此对象中复制或覆盖任何数值门限。启用时必须同时满足single-real-groove、v2 refinement、原始source-consistency和ambiguity resolution依赖；关闭时不增加候选精修或更改结果。

**Rationale**: 避免配置漂移，强制使用既有锁定物理证据。最终独立验收前不修改生产profile生成器为默认开启。

**Alternatives rejected**:

- 静默启用到single-shot v3：行为变化不可审计，且尚无新物理验收。
- 允许独立开关自动放宽依赖：可能跳过必要物理证据。

## R6 — 诊断与离线报告

**Decision**: 运行时增加有界`grooveShadowSourceDiscrimination`嵌套诊断；离线工具生成207行逐图JSON/CSV、阶段计数、输入SHA联结状态和overlay索引。候选摘要最多3项，不携带路径、人工标签或完整采样数组。原图可用时渲染代表性overlay；原图缺失时显式记录`unavailable`，不伪造图像。

**Rationale**: 根结果Schema允许开放diagnostics，嵌套独立Schema即可兼容；大证据留在Git外。逐图报告必须区分`not_evaluated`和`failed`。

## R7 — 失败阶段规范化

**Decision**: 离线追踪按实际执行证据映射为：`upstream_outer_circle`、`candidate_generation`、`groove_recognition`、`groove_ambiguity`、`polar_quality`、`groove_refinement`、`source_consistency`、`valid`。原错误码与阶段原样保留；规范化阶段不改写运行结果。

**Rationale**: 统一账本可以回答用户要求的七类根因，同时避免把终止错误码误当全部内部执行历史。若某阶段虽执行但最终被后置质量门覆盖，报告同时保留`terminalStage=polar_quality`和逐候选执行证据。

## R8 — 验收与停止条件

**Decision**: 实现可在当前开发分支提交，但生产启用、准确率结论和PLC授权均以新物理零件冻结验收为前置条件。新manifest必须提供物理sampleId、人工三态类别、图像SHA并证明与700组物理无交集；不得包含sealed part-006。

**Rationale**: 当前没有可证明物理分离的新组。没有数据时应报告依赖阻塞，而不是循环使用700张调参或制造验收数字。
