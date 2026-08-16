# Data Model: D7 v6回退首版有效性诊断

## D7ReleaseState

| 字段 | 来源 | 语义 |
|---|---|---|
| `measurementValid` | 现有feature契约 | 检测质量通过且D7业务值有限 |
| `evidenceComplete` | 现有feature契约 | A/B原始点和拟合线均可审核 |
| `evidenceAuditStatus` | 现有feature契约 | `complete/partial/unavailable/not_applicable` |
| `sourceDetector` | 现有feature契约 | 正式数值来自哪个检测器 |
| `recoveryPass` | 现有feature契约 | 是否使用受控v6回退 |
| `productionDisposition` | 现有quality契约 | 固定为`not_evaluated` |

本规格不新增运行时字段，只定义首版如何联合解释现有字段。

## 状态组合

| measurementValid | evidenceAuditStatus | 含义 | 首版权限 |
|---:|---|---|---|
| false | not_applicable | 测量失败 | 不得输出有效尺寸 |
| true | unavailable | 数值质量通过，交付证据缺失 | 仅技术/趋势用途，显式警告 |
| true | partial | 数值质量通过，仅单侧证据 | 不可称完整审核 |
| true | complete | 数值与A/B证据均存在 | 可进行人工几何审核，仍非生产OK/NG |

## 派生发布指标

- `d7MeasurementValidCount = count(measurementValid)`
- `d7EvidenceCompleteCount = count(measurementValid && evidenceComplete)`
- `d7V6FallbackCount = count(recoveryPass == "v6_original_quality")`
- `d7UnauditableValidCount = count(measurementValid && !evidenceComplete)`

这些是报告解释规则，不要求修改当前Schema。
