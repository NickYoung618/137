# Contract: D7 long paired support

## Scope

这是`hole2-current-capture-result/2`内部D7审核证据的向后兼容扩充，不改变Schema版本、业务测量列或valid语义。

## Formal raw evidence boundary

每个`features["7"].target.rawEdgeEvidence.boundaries[]`继续包含：

- `side`
- `pointsPx`: 原主窗口正式paired中点
- `transitionPairsPx`: 原外/内跃迁对
- `supportPointsPx`: 新增长范围连续paired中点；无扩展时为空
- `supportTransitionPairsPx`: 与supportPoints一一对应；无扩展时为空
- `supportEvidenceMode`

所有坐标为目标原图像素，不允许毫米换算。

## Fitted geometry boundary

`features["7"].target.fittedGeometry.boundaries[]`：

- `lineEquation`必须与扩展前完全一致；
- `segmentPointsPx`允许在连续支持范围内增长；
- 两端点必须落在lineEquation上；
- 不允许用support points重新拟合或改变D7公法线。

## Quality diagnostics

`features["7"].quality`保留：

- `candidate_boundary_support_extension_attempted`
- `candidate_boundary_support_extension_complete`
- `candidate_boundary_support_extension_contract`
- `candidate_boundary_support_sides`
- `candidate_boundary_support_lengths_target_px`

每侧诊断必须包含primary/candidate/accepted最远位置、接受点数、停止位置/原因和逐窗口诊断。

## Renderer/LabelMe

- 正式A/B标签仍为`prediction:7:boundary:A/B`；
- line points为原图坐标有限线段；
- flags增加`supportEvidenceMode`、`primaryPointCount`、`extensionPointCount`；
- v6使用`review:7:*`且`reviewOnly=true`、`equivalentToFormalBoundary=false`；
- 不生成完整零件轮廓，不读取目标真值。

## Failure protections

- 单梯度点不得进入`supportPointsPx`；
- A/B单侧新增、跨间隙孤立簇、竞争层或残差超门时，正式段保持022值；
- 扩展失败不得改变`measurementValid`、`failureReason`或`sourceDetector`；
- Phi对象和其证据字段不得变化。
