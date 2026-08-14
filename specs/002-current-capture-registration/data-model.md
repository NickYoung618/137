# Data Model: 现拍样品姿态注册与孔2尺寸检测

## Coordinate systems

- `reference_px`: 旧参考图片像素坐标，原点左上，`x` 向右、`y` 向下。
- `target_px`: 现拍目标图片像素坐标，定义同上。
- 正向映射：`target = scale * R(theta) * reference + translation`。
- 逆向映射：显式保存并由相同参数计算；验证 `reference → target → reference` 数值闭环。

## RegistrationConfig

- `schemaVersion` / `configVersion`
- `orientationsDeg`: 必含 0、90、180、270。
- 全局扫描：降采样、尺度上下限/步长、保留峰数和非极大抑制距离。
- 分组搜索：参考聚类距离、目标搜索半径/步长、最小边缘峰与显著性。
- 质量门限：最小支持组、最小空间覆盖、最大精配准角、尺度范围、残差、候选间隔和闭环误差。
- 测量门限：`7` 沿用 v6；`Φ12.2` 主半径比下限 `0.88`，仅主下界饱和时启用 `0.84` 恢复下限，并共用点数、拟合残差、边缘峰值/显著性与非饱和门。
- `7` 切线耦合门限：旧参考切线误差、目标轴最大移动量、双边界点数/残差/边缘得分和平行度。

## RegistrationSupport

- `groupId`, `labels`, `referencePoint`, `targetPoint`
- `edgePeakNormalized`, `edgeProminenceNormalized`, `offsetPx`
- `visibleFraction`, `valid`, `failureReason`

## OrientationCandidate

- `orientationDeg`, `dx`, `dy`, `scale`, `thetaDeg`
- `score`, `supportCount`, `spatialCoverage`, `medianResidualPx`, `maxResidualPx`
- `supports[]`, `valid`, `failureReasons[]`

状态：`generated → locally_scored → refined → valid|rejected`。

## RegistrationResult

- 算法/配置/契约版本与三个运行时资产哈希。
- 所有候选及其排序。
- 选中候选、候选间隔和 `registrationValid`/`failureReason`。
- `transform` 和 `inverseTransform` 分别显式表达 `reference_px_to_target_px` 与
  `target_px_to_reference_px`，并保留参考/目标图片尺寸和闭环误差。

状态：无有效候选为 `invalid`；唯一最佳候选且全部门限通过为 `valid`。

## FeatureMeasurement

- 共通：`featureCode`, `measurementValid`, `failureReason`, `sourceDetector`, `quality`。
- `7`: `reference` 和 `target` 各含无方向语义的两个端点与长度；目标测量轴由已检测 `Φ12.2` 对应切线重建，再执行双边界拟合。新路径失败时只可使用原质量状态为 `ok:dual_boundary_fit` 的 v6 有限量测。
- `quality`: `Φ12.2` 保留 `candidate_main_lower_bound_saturated`、主/最终半径比与 `candidate_recovery_pass`；`7` 回退保留新候选失败及 `candidate_fallback_pass|failure`。
- `Φ12.2`: 两坐标系各含圆心、半径、直径和圆弧支撑点。
- `referenceMeasurements`: 兼容 `d7_*`、`Phi12_2_*` 业务列，不覆盖原始 v6 诊断字典。

注册无效时两个特征均无有限几何；单特征失败不改变另一特征与注册状态。

## CurrentCaptureResult

- `runtimeInputs`: 仅 `referenceAnnotation`、`referenceImage`、`targetImage`、`configuration` 角色及哈希。
- `registration`, `features`, `referenceMeasurements`, `v6Measurements`。
- `timingMs`, `evidenceScope`, `errors[]`。
- `qualityStatus`: `complete` / `registration_invalid` / `measurement_invalid`；
  `technicalValid` 只有在注册与两特征均有效时为真，`productionDisposition`
  固定为 `not_evaluated`。

## AcceptanceReport

- 检测结果/目标图片/真值标注哈希和契约版本。
- 真值结构校验结果，必须恰为 `7` 两点 line 与 `Φ12.2` 不少于8个有限点、通过现有圆残差门的 linestrip；同时记录实际点数和拟合残差。
- `7`: 真值长度、预测长度、长度绝对误差、最佳无序端点平均/最大误差。
- `Φ12.2`: 真值拟合圆、预测圆、中心/半径/直径误差、真值点径向残差统计。
- `status`: `evaluated`、`result_invalid` 或 `input_rejected`；不得输出生产 OK/NG。
- `scope`: 固定声明单图像素诊断，不代表重复性、毫米精度或生产公差。
- `detectionSummary`: 算法/配置/结果契约版本、耗时、技术质量、方向、正/逆变换、
  候选分数/拒绝原因与逐特征质量。

## BatchQualitySummary

- 输入是可重复的 `NAME=/external/directory` 分组，无目标标注角色。
- 按总体和分组统计执行成功、注册有效、技术完整、逐特征有效、方向、候选/特征
  失败原因与耗时。
- 逐图结果写入仓库外 JSONL，汇总写入仓库外 JSON；均不是产品 OK/NG。
