# Data Model: 全画面壳体外圆唯一定位

## CircleLocatorConfig

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | 固定`full-frame-circle-locator-config/1` |
| `enabled` | boolean | 首版仅`single_real_groove`允许为true |
| `threshold_version` | string | 非空、随判据变更 |
| `downsample_step` | integer | 有界正整数；不得让最小候选直径低于稳定采样数 |
| `threshold_method` | string | 首版固定`otsu` |
| `threshold_offsets` | integer[] | Otsu阈值的有界诊断偏移，不是逐图真值 |
| `allowed_center_region_normalized` | 4 finite numbers | `[xmin,ymin,xmax,ymax]`，有序且在`[0,1]` |
| `min_scale`, `max_scale` | number | 相对参考外圆的正数有序范围 |
| `min_bbox_aspect_ratio` | number | `(0,1]` |
| `min_fill_ratio`, `max_fill_ratio` | number | `[0,1]`内有序 |
| `min_border_clearance_ratio` | number | 非负，相对候选半径 |
| `max_component_candidates` | integer | 严格正整数硬上限 |
| `dedup_center_distance_ratio` | number | 正数，相对候选半径 |
| `dedup_radius_difference_ratio` | number | 正数，相对候选半径 |
| `min_score_margin` | number | `[0,1]` |
| `coarse_physical_circle` | object | 180射线数量、质量门和版本 |

配置状态：`disabled | validated | invalid`。显式ROI与`enabled=true`同时出现时为`invalid`。

## ComponentProposal

| Field | Type | Meaning |
|---|---|---|
| `proposalId` | string | 单图内稳定编号`proposal-001...` |
| `threshold` | integer | 实际自适应阈值 |
| `bboxNormalized` | 4 numbers | 原图归一化边界框 |
| `centerX`, `centerY`, `radiusPx` | number | 从边界框得到的粗先验，非测量圆 |
| `referenceScale` | number | `radiusPx/referencePhysicalRadiusPx` |
| `componentPixelCount` | integer | 低分辨率连通像素数 |
| `bboxAspectRatio` | number | 短边/长边 |
| `fillRatio` | number | 连通像素/边界框面积 |
| `borderClearanceRatio` | number | 到图像边界最小距离/粗半径 |
| `failedChecks` | string[] | 中心范围、尺度、形状、填充、边界等 |
| `status` | enum | `eligible | rejected` |

`ComponentProposal`永远不是下游物理圆，不能直接用于槽或角度。

## SparseCircleHypothesis

| Field | Type | Meaning |
|---|---|---|
| `candidateId` | string | 去重前稳定编号`circle-candidate-001...` |
| `rank` | integer/null | 稀疏物理候选质量排名（从1开始）；未获得可评分物理圆时为空 |
| `proposalId` | string | 来源提议 |
| `coarsePhysicalCircle` | object/null | 稀疏gyj拟合结果 |
| `edgePointCount`, `inlierCount` | integer | 稀疏射线证据 |
| `inlierRatio`, `angularCoverage` | number | `[0,1]` |
| `residualP95Px`, `centerShiftPx` | number/null | 质量指标 |
| `scoreComponents` | object | 覆盖、内点、残差、先验一致性归一化分量 |
| `score` | number/null | 可复算总分 |
| `failedChecks` | string[] | 稀疏质量门失败原因 |
| `status` | enum | `accepted | rejected` |

## CircleHypothesisCluster

同一物理圆的多个稀疏候选集合。包含`clusterId`、成员ID、代表候选、中心/半径离散度和代表分数。若中心或半径离散度超过去重门，则不得合并。

## CircleSelectionDecision

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | string | `full-frame-circle-localization/1` |
| `strategy` | string | `otsu-components+sparse-gyj+full-gyj` |
| `status` | enum | `accepted | not_found | ambiguous | overflow | refinement_failed` |
| `bestCandidateId`, `secondCandidateId` | string/null | 按分数和稳定ID排序 |
| `bestScore`, `secondBestScore`, `scoreMargin` | number/null | 可复算；无次候选时`second*`为空 |
| `selectedCandidateId` | string/null | 仅`accepted`非空 |
| `componentProposals` | array | 所有提议，包括拒绝项 |
| `circleCandidates` | array | 所有稀疏评估结果 |
| `clusters` | array | 去重结果 |
| `finalPhysicalCircle` | object/null | 仅最终720射线通过后存在 |
| `failedChecks` | string[] | 稳定失败原因 |
| `timingMs` | object | 发现、稀疏评估、选择、最终精修 |

状态转换：

```text
received
 → proposals_extracted
 → sparse_candidates_assessed
 → hypotheses_deduplicated
 → unique_candidate_selected
 → physical_outer_circle_refined
 → accepted
```

任一步可转移到`not_found | ambiguous | overflow | refinement_failed`，均为终态并阻止下游。

## LocalizationDiagnosticRun

绑定数据集内容哈希、算法/配置版本、锁定gyj源码哈希、硬件、逐图`CircleSelectionDecision`、完整结果、冷启动/稳定态耗时、墙钟吞吐、峰值RSS和审阅产物相对路径。它是开发证据，不是角度truth。

## ReviewedRealCaseAnnotation

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | string | `slot-pose-real-case-annotation/1` |
| `imageRelativePath` | string | 安全相对路径，不允许绝对路径或`..` |
| `imageSha256` | string | 64位小写十六进制，与检测输入严格一致 |
| `labelmeRelativePath` | string | 外置标注根下安全相对路径 |
| `labelmeSha256` | string | 标注内容校验和 |
| `annotationVersion` | string | 非空版本ID |
| `annotatorId`, `reviewerId` | string | 非空且必须不同 |
| `humanVerified` | boolean | 进入验收必须为true |
| `independentFromAlgorithm` | boolean | 进入验收必须为true |
| `physicalCircleSource` | enum | `manual_circle | manual_visible_arc_fit` |
| `grooveSource` | enum | `manual_open_boundary` |
| `reviewStatus` | enum | `template | draft | rejected | reviewed` |
| `rejectionReasons` | string[] | 缺失shape、非有限点、覆盖不足、槽不内凹等 |
| `split` | enum | `development | tuning | validation | acceptance` |

LabelMe最少shape：

- `physical_outer_circle_truth`，`shape_type=circle`，两个有限点；或者更高精度的`physical_outer_circle_visible_arc_manual`，`shape_type=linestrip`且通过现有圆拟合质量门；
- `target_groove_open_boundary_manual`，`shape_type=linestrip`、至少6个有限点，首尾点是槽口两端，并通过连续性、靠圆和内凹门。

`template`和`draft`可用于管理标注进度，但`evaluationEligible=false`。算法预标只能使用`algorithm_suggestion_*`标签并固定`formal_truth=false`，人工复核不得通过简单改名自动完成。

## AnnotatedDetectionComparison

与一个`ReviewedRealCaseAnnotation`和同图自动结果绑定，字段包括人工/自动圆、圆心`dx/dy/distance`、半径有符号/绝对差、人工/自动槽口中点角、环形角差、人工/自动象限、人工/自动85度状态、可评估状态和空值原因。失败检测或不合格标注中的数值保持`null`，不得填0。

## StaticRepeatabilityGroup

| Field | Meaning |
|---|---|
| `groupKey` | `split + physicalSampleId + position + conditionId`，必须来自显式采集记录 |
| `expectedRepeatCount`, `validRepeatCount` | 期望和实际有效重复数 |
| `residualCircularRangeDeg` | 对`automaticAngle - humanAngle`环形残差围绕组均值展开后的极差 |
| `residualStdDeg` | 上述展开残差的总体标准差 |
| `residualAbsoluteDeviationP95Deg` | 相对环形残差均值的绝对偏差P95 |
| `status` | `EVALUATED | NOT_EVALUATED` |
| `reason` | 分组未确认、标注不足、检测失败或重复数不足 |

不同真值角度组不得合并计算原始角度极差；重复性限值未由质量负责人确认时只报告数值，不给PASS/FAIL。
