# Research: A 端面质量分层与批量评估

## Decision 1: 核心质量项来源

**Decision**: 以 `core.py` 实际写出的 `*.quality.measurement_valid`、`*.detect.source`、
`*.quality.anomaly_reason` 和伴随质量字段作为不可改写的特征测量事实。

**Rationale**: 用户明确禁止修改桌面核心或把全部无效项强行改有效。核心输出已经能逐项追踪检测路径。

**Alternatives considered**: 在适配层重算并覆盖核心有效位；会掩盖真实失败，拒绝采用。

### Core source traceability

| Feature/source | Core path | Invalid condition | Observable fields | Classification |
| --- | --- | --- | --- | --- |
| `19��`, `30��` / `short_line_transform_fallback` | `detect_non_circle_points_with_quality` → `refine_short_line` | 线长小于 4 px、采样全越界、最佳峰位于搜索边界，或峰值 `< max(1.4×中位值, 中位值+5)` 中至少一项；核心只公开聚合原因 | `measurement_valid`, `anomaly_reason=short_line_lateral_edge_not_found`, `detect.source` | feature measurement |
| `46` / `d46_transform_fallback` | `refine_d46_radial_line` | 径向导数模板最佳 NCC `< 0.55` | `d46_ncc_score`, `d46_radial_offset_px`, `measurement_valid`, `anomaly_reason=d46_radial_low_score` | feature measurement |
| `M78`, `��80`, `��86` / `template` | `detect_template_locked_circle_candidate` → `detect_circle_with_quality` | 有外环锚点时模板分数 `< 0.35` 使用锚点回退并先标无效；只有径向候选至少 180 点、残差 `≤4 px`，且模板先验偏差 `>6 px`、径向候选至少好 `1 px` 才恢复有效 | template/radial score、offset、fallback、point count、residual、deviation、source、reason | feature measurement |
| inner circle | `detect_inner_hole_circle_with_quality` | 有效边缘点 `<8` | edge point count/source/reason | feature measurement by default |
| outer circle | `detect_outer_anchor_circle_with_quality` | 有效边缘点 `<8` 或拟合非有限 | edge point count/source/reason | feature measurement by default |

参考标注中的 19、30 长度约为 44.80 px 和 26.20 px，因此进入 `≤80 px` 的短线分支。参考图实算
二者均输出 `short_line_lateral_edge_not_found`；这证明它们不能作为默认端面定位门禁。

## Decision 2: 端面定位质量定义

**Decision**: 默认定位质量只检查 `transform.target_center_x_px`、`target_center_y_px`、`scale`、
`rotation_deg` 有限，尺度在配置范围内，中心位于目标图范围内，且定位方法以受控前缀开头。默认
`requiredFeatureLabels=[]`。

**Rationale**: 全局 `estimate_global_transform` 在各特征测量之前独立产生变换；19、30、46 和三个中间环
的后续测量失败不代表端面未定位。策略仍允许现场评审后显式增加必需特征，但不能隐式一票否决。

**Alternatives considered**: 把所有核心特征有效位 AND 为定位有效；已导致 A2 的 0/25，拒绝采用。

## Decision 3: 定位策略与核心门限边界

**Decision**: 配置化的是适配层定位门限和必需特征清单；46、短线和中间环的内部门限继续由不变的
核心决定，并只在诊断目录中公开。

**Rationale**: 在不修改核心的条件下，适配层不应伪造一套同名测量判定。定位策略可版本化，核心
测量判定则由核心哈希固定。

**Alternatives considered**: 允许配置覆盖 `0.55/0.35`；这会造成“核心无效但策略有效”的双义，暂不采用。

## Decision 4: 契约语义

**Decision**: 升级到 `a-end-face-result/2`：`result.valid` 与 `result.localization.valid` 同义；新增
`measurementCompleteness.allValid` 和逐特征 `featureQuality`。保留原始 `measurements`。

**Rationale**: 版本升级避免静默改变 v1 的 `valid=所有特征都有效` 语义，同时为集成方提供明确迁移点。

**Alternatives considered**: 保持 v1 并悄悄改变 `valid`；不兼容且不可审计，拒绝采用。

## Decision 5: 批量处理和离线重统计

**Decision**: 批量执行前复用 Manifest 全属性/哈希验证；逐图结果写 JSONL；汇总函数只依赖结果对象，
所以本机可只传 Manifest 指纹和结果证据，不传图片。

**Rationale**: 同时满足真实外置 A2 执行与服务器无图复现，且避免将大型单个 JSON 数组一次载入内存。

**Alternatives considered**: 把图片或压缩包上传服务器；违反用户要求和 Constitution。

## Decision 6: A2 证据状态

**Decision**: 将用户反馈写为 `user-reported-a2-summary/1` 小型证据文件，明确 `manifestSha256=null`、
没有逐图原始结果，不把它宣称为服务器重新检测结果。

**Rationale**: 既可锁定验收计数，也不会虚构缺失的 Manifest 指纹或逐图诊断。

**Alternatives considered**: 生成伪造逐图路径/哈希；破坏溯源，拒绝采用。
