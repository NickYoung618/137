# Data Model: A2 多组静态重复性与过渡盲测治理

## CanonicalInventoryRecord

| Field | Type | Rule |
|---|---|---|
| relativePath | safe relative string | 相对一个显式dataRoot，唯一 |
| datasetClass | normal/bad | 目录兼容分类，不等于poseUsable |
| sourceImageSha256 | 64位小写hex | 700行唯一且与源文件可核验 |
| captureSequence | positive integer | 类内或全局序号，来源明确 |
| captureTimestamp | string/null | 原始证据；不得单独制造condition |
| sampleId/conditionId/repeatIndex | null or confirmed value | draft阶段允许为空 |
| split | unassigned/purpose | draft统一unassigned |

状态：`DRAFT`（任一分组字段空）→ 经人工记录关联后生成独立`ConfirmedGroupingRecord`；inventory原件不覆盖。

## ConfirmedGroupingRecord

| Field | Type | Rule |
|---|---|---|
| relativePath/sourceImageSha256 | inventory identity | 必须精确一一覆盖 |
| sampleId | non-empty string | 物理零件；未知跨class映射时class-qualified |
| conditionId | non-empty string | 同一次固定摆放、角度与工况 |
| repeatIndex | positive integer | condition内从1连续 |
| split | unassigned/development/validation/test/acceptance | 同sample不得跨purpose |
| groupingAuthority | non-empty string | 采集负责人或批准角色 |
| groupingProvenance | non-empty string | 采集记录/复核批次，不得来自算法结果 |

## StaticGroupEligibility

键：`sampleId + conditionId`。

- datasetClasses、frameCount、validSemanticsCount。
- status：`ELIGIBLE`或`EXCLUDED`。
- exclusionReasons：`FRAME_COUNT_LT_20`、`REPEAT_NOT_CONTIGUOUS`、`BAD_SEMANTICS_UNCONFIRMED`、`GROUPING_NOT_CONFIRMED`、`SPLIT_LEAKAGE`等。
- authoritative：只有全部门通过为true。

normal末组关系：`normal:part-025`包含`condition-a`的18帧和`condition-b`的2帧；两个condition均排除，但sample记录完整保留。

## StaticGroupResult

- identity：sample、condition、class、purpose、frameCount。
- eligibility：资格状态与原因。
- detection：valid/failed count、validRate、guidance/direction/error计数。
- angle：n、circularMeanDeg、circularRangeDeg、sampleStdDeg、p95AbsoluteResidualDeg。
- geometry：circleCenterX/Y、radius、grooveOpeningX/Y各自n/range/std/p95AbsoluteResidual。
- timing：n/P50/P95/max elapsedMs。
- guidanceClass：`TARGET_NEAR`、`NEEDS_CLOCKWISE`、`NEEDS_COUNTERCLOCKWISE`、`MIXED_OR_UNAVAILABLE`。

## StaticRepeatabilitySummary

- eligible/excluded group和frame计数。
- authoritative groups only与all diagnostic groups分区。
- pooledWithinGroupAngleResidual：按每组圆均值中心化后池化。
- worstGroup：按angle range/std/P95和最低validRate分别标识。
- guidanceCoverage：三类工况的组数与`COMPLETE|BLOCKED`。
- badSemantics：权威覆盖与阻塞数。

## TransitionalBlindLock

- schemaVersion=`a2-transitional-blind-lock/1`。
- blindStatus=`NON_STRICT_TRANSITIONAL`；priorExposure=true。
- selectionAlgorithm/version/salt、candidateSampleCount、selectedSampleId、selectedConditionIds。
- selectedImageCount与排序后image SHA列表。
- sourceManifestSha256、blindManifestSha256、lockPayloadSha256。
- maxExecutionCount=1、executionCount=0；执行结果由独立外置记录更新，不覆盖锁。

状态：`PLANNED` → 发布候选时外置执行记录`EXECUTED_ONCE`；重复执行请求拒绝。严格test状态不由此实体产生。
