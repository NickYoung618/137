# Data Model: A 端面独立检测 CLI

## InspectionInput

| Field | Type | Rules |
| --- | --- | --- |
| taskId | string | 非空；未提供时由图像名生成 |
| image | path | 必须为可读文件 |
| annotation | path | 必须为可读 LabelMe JSON |
| reference | path | 由标注 `imagePath` 解析且必须可读 |
| pixelSize | number | 大于 0；默认 1 |

## InspectionResult

| Field | Type | Rules |
| --- | --- | --- |
| schemaVersion | string | 固定 `a-end-face-result/1` |
| technicalStatus | enum | `succeeded` 或 `failed` |
| input | object | 成功时包含三项路径和 SHA-256 |
| algorithm | object | 名称、版本和核心 SHA-256 |
| result | object/null | 失败时必须为 null |
| error | object/null | 成功时必须为 null |

## MeasurementResult

| Field | Type | Rules |
| --- | --- | --- |
| valid | boolean | 无无效质量特征时为真 |
| pixelSize | number | 本次调用比例 |
| shiftMethod | string | 核心返回的配准方法 |
| invalidFeatures | string[] | 按名称排序且无重复 |
| measurements | object | 核心字段原名；非有限值为 null |

## State Transitions

`input validated` → `reference built` → `measurements detected` → `succeeded`。
任一阶段异常直接进入 `failed`；失败状态不包含量测对象。
