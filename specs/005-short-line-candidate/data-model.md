# Data Model: A 端面短线候选诊断与测量改进

## CandidateConfiguration

| Field | Type | Rules |
| --- | --- | --- |
| schemaVersion | string | `a-end-face-short-line-candidate-config/1` |
| candidateId | string | 非空；规则变化必须更换标识或版本 |
| algorithmVersion | string | 非空语义版本 |
| features | string[] | 规范特征，v1 必须恰为 `19`,`30` 且无重复 |
| template | object | 横/纵采样范围与步长；均有限、正数且形成有效 ROI |
| search | object | 粗/细方向、纵向、横向范围与步长；细搜索不得超出粗搜索保护边界 |
| gates | object | 覆盖、对比、梯度、相关、稳健显著性、分离峰及最大修正规则 |
| sha256 | derived string | 对规范化配置 JSON 计算，不由调用方提供 |

## ShortLineDiagnostic

| Field | Type | Rules |
| --- | --- | --- |
| diagnosticVersion | string | `short-line-diagnostic/1` |
| feature/canonicalFeature | string | 原始核心前缀及规范 19/30 身份 |
| predicted | geometry | 来自旧核心量测，保持其数值 |
| roi | object | 目标 ROI 边界、有效覆盖、灰度对比度、梯度 P50/P90/max |
| coreSearch | object | `[-12,+12]`、剖面摘要、peak/median/threshold/boundary/fallbackReason |
| candidateSearch | object | 搜索范围、最佳/分离次佳、相关分布和边界命中情况 |
| checks | Check[] | 每个检查有 id、required、rule、observed、passed |
| failedChecks | string[] | 必须等于 required 且失败的检查 id |
| failureCategories | string[] | 将失败检查归并为 no_edge、boundary_peak、low_prominence、competing_peak、insufficient_coverage、fit_instability、direction_deviation 等可批量统计类别 |

`coreSearch` 复算结果仅用于解释，不更改核心返回；若复算与核心来源矛盾，增加
`core_path_consistency=false` 并使候选失败。

## CandidateMeasurement

| Field | Type | Rules |
| --- | --- | --- |
| candidateValid | boolean | 所有 required checks 通过 |
| source | string | `reference-gradient-registration-v1` |
| target | geometry/null | 有效时含 x1/y1/x2/y2/length/angle；无效时为 null |
| reference | geometry/null | 通过核心变换逆变换后的同一候选几何；无效时为 null |
| deltaFromCore | object/null | midpoint、angle、endpoint 及 length 差异；无效时为 null |
| elapsedMs | number | 仅候选/诊断耗时，有限非负 |

候选保持参考标注长度经核心尺度变换后的纵向长度；方向和中点来自图像模板搜索。

## FeatureComparison

| Field | Type | Rules |
| --- | --- | --- |
| feature/canonicalFeature | string | 原始和规范身份 |
| core | object | coreValid、source、reason、旧 target/reference geometry、原始质量字段 |
| candidate | CandidateMeasurement | 独立状态和几何 |
| diagnostic | ShortLineDiagnostic | 完整证据与失败保护 |
| transition | enum | `both_valid`,`recovered`,`regressed`,`both_invalid` |

状态表：

| coreValid | candidateValid | transition |
| --- | --- | --- |
| true | true | `both_valid` |
| false | true | `recovered` |
| true | false | `regressed` |
| false | false | `both_invalid` |

## SingleImageResultV3

继承 v2 的技术、定位、测量完整性、逐特征质量和原始量测语义；成功结果新增
`shortLineCandidates`（按原始标签索引的 FeatureComparison）。候选禁用时允许为空对象，但默认 CLI
配置会生成 19/30。算法追溯新增候选 id/version/config SHA-256，不修改 coreSourceSha256。

## PerImageComparisonRecord

| Field | Type | Rules |
| --- | --- | --- |
| schemaVersion | string | `a-end-face-short-line-comparison/1` |
| taskId | string | 与 Manifest imageId、既有结果 taskId 完全相同 |
| input | object | 外置相对路径、图片 SHA-256、宽高；无图片字节 |
| provenance | object | annotation/reference/core/config 指纹 |
| baselineSchemaVersion | string | 接受 `a-end-face-result/2` 或 `/3` |
| technicalStatus | enum | `compared` 或 `baseline_failed` |
| coreFeatureStatus | object | 至少记录 19、30、46、M78、80、86 的旧 coreValid/source/reason |
| features | object/null | compared 时为 19/30 FeatureComparison；基线技术失败时为 null |
| error | object/null | 基线失败原因，不伪造候选 |

## BatchComparisonSummary

| Field | Type | Rules |
| --- | --- | --- |
| schemaVersion | string | `a-end-face-short-line-batch-summary/1` |
| dataset/provenance | object | dataset、Manifest、比较 JSONL、核心和配置指纹 |
| imageCount | integer | 比较记录总数 |
| comparisonStatus | CountRate | compared/baselineFailed |
| candidateFeatures | object | 19/30 的 coreValid、candidateValid、四种迁移及失败检查分布 |
| priorityCoreFeatures | object | 19、30、46、M78、80、86 的旧有效/无效/来源/原因计数 |
| deltaMetrics | object | 仅候选有效记录的 midpoint/angle 差异 min/mean/max |
| acceptance | object | `regressed==0` 及 `recovered>0` 的独立布尔检查，不改写结果 |

## Lifecycle

`Manifest + baseline JSONL preflight` → `reference/config loaded` → `per-image diagnostic` →
`candidate gated` → `comparison JSONL written` → `image-free summary rebuilt`。

任一全局预检失败时没有逐图输出；单个 baseline 技术失败形成可汇总的 `baseline_failed` 记录，但不运行候选。
