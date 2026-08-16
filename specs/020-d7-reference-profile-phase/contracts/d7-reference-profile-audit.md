# Contract: D7 Reference Profile Audit

诊断结果对象必须包含：

```json
{
  "contractVersion": "d7-reference-profile-audit/1",
  "candidateValid": false,
  "failureReason": "string-or-null",
  "formalMeasurementUpdated": false,
  "measurementTargetPx": null,
  "boundaryA": {},
  "boundaryB": {},
  "parallelismDeg": null
}
```

每侧必须包含`valid`、`failureReason`、`supportCount`、`scoreMedian`、`scoreMarginMedian`、
`shiftMedianTargetPx`、`shiftMadTargetPx`、`fitResidualTargetPx`、`axisCosine`和证据坐标。

约束：

- `formalMeasurementUpdated`永远为`false`。
- 非有限数值序列化为`null`。
- 候选无效时不得提供貌似有效的测量值。
- 对象不得包含目标真值、标称毫米值或生产OK/NG。

当CLI显式提供仓库外`--target-labelme`时，报告可追加
`formalEvidenceTruthComparison`。该对象只在正式检测和独立候选均冻结后生成，必须包含：

- `formalMeasurementUpdated=false`；
- A/B各自的`rawPairCount`、`selectedPairCount`及既有残差门来源；
- `outer=0_midpoint=0.5_inner=1`定义下的人工相位分布；
- 外过渡、中点、内过渡到人工线的有符号分布和绝对距离中位数；
- 正式宽度、人工宽度和绝对差。

该对象是离线验收证据，不得反馈给候选排序、正式测量值或有效性判断。
