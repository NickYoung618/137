# Data Model: A 端面质量分层与批量评估

## QualityPolicy

| Field | Type | Rules |
| --- | --- | --- |
| schemaVersion | string | `a-end-face-quality-policy/1` |
| policyId | string | 非空、随规则变更版本化 |
| localization.requiredFiniteMetrics | string[] | 必须包含中心、尺度、旋转 |
| localization.scaleRange | [number, number] | 有限、正数、下界不大于上界 |
| localization.centerMarginPx | number | 非负 |
| localization.allowedMethodPrefixes | string[] | 非空字符串 |
| localization.orientationEvidence | object | polar rotation score 或 notch prominence 至少一项过门限 |
| localization.requiredFeatureLabels | string[] | 默认空；显式配置才可影响定位 |

## LocalizationQuality

| Field | Type | Rules |
| --- | --- | --- |
| valid | boolean | 等于全部 required checks 的 AND |
| policyId/policySha256 | string | 规则追溯 |
| checks | Check[] | 每条含 id、passed、rule、observed |
| failedChecks | string[] | `passed=false` 的检查 id |

## FeatureQuality

| Field | Type | Rules |
| --- | --- | --- |
| feature | string | 核心输出前缀 |
| canonicalFeature | string | 去除已知损坏直径符号后的稳定统计名；不替代原始 feature |
| classification | enum | `feature_measurement` 或 `localization_required` |
| coreValid | boolean | 只从核心 `measurement_valid` 得到，不可覆盖 |
| source | string/null | 核心 `detect.source` |
| reason | string/null | 核心 `anomaly_reason` |
| fields | object | 该特征全部 `quality.*` 字段，严格 JSON |
| diagnostic | object | 检测路径、固定条件、观测门限字段 |

## MeasurementCompleteness

| Field | Type | Rules |
| --- | --- | --- |
| allValid | boolean | total>0 且 invalidCount=0；无质量项时为 false |
| total/validCount/invalidCount | integer | 非负且加和一致 |
| invalidFeatures | string[] | 排序、无重复 |

## SingleImageResultV2

技术失败时 `result=null`。技术成功时 `result.valid == result.localization.valid`，同时包含定位质量、
测量完整性、逐特征质量和原始 192 项（或实际数量）量测。技术成功不蕴含定位或所有测量有效。

## BatchQualitySummary

| Field | Type | Rules |
| --- | --- | --- |
| dataset | object | datasetId、fingerprint、manifestSha256 |
| imageCount | integer | 结果总数 |
| technical/localization/measurementCompleteness | CountRate | total、valid、invalid、rate |
| timing | object | 有效耗时数量、mean/min/max ms |
| features | object | 每特征 total/invalid/count rate/source/reason 分布 |

## State Transitions

`manifest validated` → `reference/policy loaded` → `core executed per image` → `quality adapted` →
`JSONL written` → `summary aggregated`。Manifest 失败在核心执行前终止；单图技术失败仍可进入批量汇总。
