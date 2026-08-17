# Research: 真槽同源性误拒裁决

## Decision 1: 保留原门，新增独立有效裁决

- **Decision**: 原`groove-sidewall-source-consistency/1`输出完全不变；实验裁决以独立payload输出original/effective状态。
- **Rationale**: 145证明contrast不对称可在真槽上出现，part-019证明单纯放宽contrast会恢复混合假阳性。保留原证据才能审计。
- **Rejected**: 把0.12改成0.20；删除contrast check；直接把`sourceConsistency.status`从rejected改accepted。

## Decision 2: 仅裁决精确contrast-only失败

- **Decision**: 失败集合必须精确等于`[edge_contrast_asymmetry]`，所有非contrast原检查必须通过。
- **Rationale**: 不让二级裁决越过梯度、剖面、径向深度、端点或遮挡失败。
- **Rejected**: 任何“只要综合分数高”的加权越门方案。

## Decision 3: 复用已冻结的严格端点结构证据

- **Decision**: 二级裁决使用现有development candidate已版本化的`endpointStructureDifference<=0.05`证据，不在022中根据145重调。
- **Rationale**: part-008现有帧约0.019–0.023，part-019已确认混合边约0.076–0.081；0.05在021就已作为默认关闭开发候选门，本轮只将其固化为实验裁决证据，不称泛化。
- **Rejected**: 根据145的具体数值设置更紧的样本专用门；用角度区间或sampleId区分正负例。

## Decision 4: 默认关闭，开启即代表允许实验图像姿态释放

- **Decision**: 新配置不存在/关闭时完全没有输出变化；只在`enabled=true`且裁决`ACCEPTED_OVERRIDE`时继续现有姿态链。
- **Rationale**: 这是对运行时valid语义的真实改变，必须显式、可回退、不影响默认。
- **Rejected**: 修改全局默认；让旧`sidewall_source_consistency_candidate/1`悄然升权。旧candidate仍`posePromotionAllowed=false`。

## Decision 5: 人工真值只用于离线裁决

- **Decision**: runtime纯函数不接收身份、路径或人工几何；145/147/part-019只在Git外回放报告中按SHA裁决。
- **Rationale**: 防止真值泄漏、文件名过拟合和样本专用规则。

## Decision 6: 不重做图像计算

- **Decision**: 裁决只读已产生的source-consistency标量与checks。
- **Rationale**: 可以控制延迟在微秒/毫秒级，不重复全图解码、拟圆、极坐标或侧壁精修。
