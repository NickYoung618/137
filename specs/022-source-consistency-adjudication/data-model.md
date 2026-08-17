# Data Model: 真槽同源性误拒裁决

## SourceConsistencyAdjudicationConfig

- `schemaVersion`: `source-consistency-adjudication/1`
- `enabled`: 默认false
- `thresholdVersion`: 版本化二级证据名
- `developmentOnly`: 恒true
- `maxEndpointStructureDifference`: 有限`[0,1]`，初版冻结0.05

不包含imageId、sampleId、文件名、固定角、人工几何或PLC参数。

## OriginalSourceConsistency

引用现有`groove-sidewall-source-consistency/1`：

- `status`: `not_evaluated | disabled | accepted | rejected`
- `metrics`: contrast/gradient/profile/radial coverage/endpoint structure数值
- `checks`: 每项`checkId/metric/value/threshold/thresholdKind/passed`
- `failedChecks`: 原失败原因列表

对象在裁决前后必须深拷贝等值，不可改写。

## SourceConsistencyAdjudication

- `schemaVersion`: `source-consistency-adjudication/1`
- `thresholdVersion`
- `enabled`: true
- `developmentOnly`: true
- `authoritative`: false
- `productionDefaultAllowed`: false
- `plcAllowed`: false
- `manualTruthAppliedAtRuntime`: false
- `decision`: `NOT_EVALUATED | NOT_NEEDED | REJECTED | ACCEPTED_OVERRIDE`
- `originalStatus`
- `effectiveStatus`: `accepted | rejected | not_evaluated`
- `originalFailedChecks`: 原列表的值拷贝
- `metrics.endpointStructureDifference`
- `checks`: 精确contrast-only、其他原检查、严格端点结构三类检查
- `failedChecks`
- `imagePoseReleaseAllowed`: 仅`ACCEPTED_OVERRIDE`为true

## EffectiveGrooveRefinement

不新建几何，仅增加裁决payload和有效判断：

- 原`sourceConsistency`始终保留。
- `sourceConsistencyAdjudication`只在显式配置存在且enabled时存在。
- effective accepted = 原accepted，或裁决`ACCEPTED_OVERRIDE`。
- 当effective rejected/not_evaluated时，原`GROOVE_SOURCE_INCONSISTENT`失败语义不变。

## State Transitions

```text
config absent/disabled -> legacy path, no adjudication field
original accepted      -> NOT_NEEDED, effective accepted
original rejected:
  exact contrast-only + all other checks + strict endpoint pass
                         -> ACCEPTED_OVERRIDE, effective accepted
  otherwise              -> REJECTED, effective rejected
missing/invalid evidence -> NOT_EVALUATED, effective not_evaluated
```

## Truth-bound Offline Evaluation

- 145: 正式人工角`29.591762332111°`，可评价runtime候选角误差。
- 147: 可裁决同源双壁/端点，不评价最终角精度。
- part-019: 混合边负例，必须保持无姿态。

上述身份与数值不存在于运行时配置或函数签名中。
