# Data Model: A2 回放验收与根因加固

## FinalReplayOutcome

| Field | Type | Rule |
|---|---|---|
| imageId | string | Manifest内唯一 |
| valid | boolean | 最终动作有效性 |
| detectionStatus | enum | `DETECTED`或`DETECTION_FAILED`，与valid一致 |
| guidanceStatus | enum | valid时为needs/in-position；失败时`NOT_AVAILABLE` |
| current/correction | number or null | valid时有限；失败时null |
| rotationDirection | enum or null | valid时CW/CCW/NONE；失败时null |
| errorCode/errorStage | string or null | valid时null；失败时稳定码/阶段 |

状态约束：final outcome永远覆盖IntermediateDiagnosticOutcome的动作语义。

## IntermediateDiagnosticOutcome

包含circle localization、physical circle、raw candidates、groove recognition、groove refinement、single groove pose和pre-quality guidance。它可以在最终失败时保留数值，但字段必须显式标记`authoritative=false`，不得进入最终动作计数。

## DatasetSemanticsRecord

| Field | Type | Rule |
|---|---|---|
| relativePath | safe relative string | CSV与Manifest键，唯一 |
| datasetClass | normal/bad | 兼容数据分层，不等于姿态可用性 |
| productDisposition | PASS/FAIL/UNKNOWN | 产品质量 |
| imageDisposition | USABLE/UNUSABLE/UNKNOWN | 图像可测性 |
| poseUsable | true/false/null | 是否允许姿态引导；null为未知 |
| authority | string/null | poseUsable非空时必填 |
| provenance | string/null | poseUsable非空时必填，不能是算法自身结果 |

关系：一条semantics对应一个Manifest图像。显式CSV存在时要求全覆盖；未知项用UNKNOWN/null而不是缺行。

## SourceConfigurationIdentity

- sourceSha256：原配置字节哈希。
- configId：运行批次的人类可读标识。
- sourcePath：仅运行环境使用，不进入有效算法身份。

## EffectiveConfigurationIdentity

- project/schemaVersion。
- pose：完整有效姿态配置。
- detector：完整默认展开、严格校验后的配置。
- legacyAssets：只含source/annotation/reference SHA-256。
- effectiveSha256：上述对象按UTF-8、键排序、无非有限数、稳定分隔符序列化后的SHA-256。

同一行为的省略默认/显式默认输入必须得到同一effectiveSha256。

## GrooveResolutionAttempt

| Field | Type | Rule |
|---|---|---|
| schemaVersion | const | `single-groove-refinement-resolution/1` |
| enabled | boolean | 默认false |
| inputCandidateIds | array | 已通过粗真槽门，稳定顺序 |
| maxCandidates | integer | 1..3 |
| attempts | array | 每候选完整refinement诊断 |
| survivorCandidateIds | array | refinement status accepted |
| status | enum | disabled/not_needed/resolved/failed/ambiguous/over_limit |
| selectedCandidateId | string/null | resolved时唯一，其他null |

状态转换：

```text
disabled -> legacy cardinality behavior
enabled + input=1 -> not_needed -> existing refinement
enabled + input>max -> over_limit -> fail closed
enabled + 2..max -> refine each
  survivors=1 -> resolved -> pose
  survivors=0 -> failed -> no guidance
  survivors>1 -> ambiguous -> no guidance
```

## ReplayAudit

- identity：schema、dataset id/fingerprint、result count、source/effective config hashes。
- finalOutcome：权威状态/方向/error计数与一致性错误。
- intermediateOutcome：pre-quality geometry/guidance计数，明确非权威。
- datasetSemantics：class计数、poseUsable覆盖、authority/provenance覆盖和blockers。
- stageFunnels：按class分圆提案、稀疏圆、最终圆、raw槽、groove、refinement、quality、final valid。
- conditionalBadMetric：按datasetClass，仅诊断。
- authoritativePoseMetric：只消费poseUsable；无标签为BLOCKED。
- thresholdMargins：observed值与effective threshold/margin，不生成replacement threshold。
- repeatability：显式分组才EVALUATED，否则NOT_EVALUATED。
- annotationQueue：stage、count、minimumAnnotation、blockedDecision。
- performance：audit wall、records、可用algorithm elapsed数量。
