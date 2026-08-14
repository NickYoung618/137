# Implementation Plan: 孔2批量诊断与定向恢复

## Architecture

继续复用 `algorithms/hole_2/main.py` v6 和
`algorithms/hole_2/current_capture.py` 适配层。新增诊断字段、离线分析工具和
Mac 全量脚本；后续恢复器作为只在特定失败原因触发的独立候选层。

## Delivery order

1. 纯诊断：不改状态/变换/量测，提交并推送。
2. 注册 `no_valid_candidate` 条件恢复，控制帧防回归，提交并推送。
3. `Φ12.2` 饱和维度恢复，提交并推送。
4. 尺寸7多带聚合，提交并推送。
5. 几何一致性、9帧对照、单图精度和全套门，提交并推送。
6. 移除77点验收假设，增加复用现有拟圆的 LabelMe 部分圆弧补全 CLI、契约、外置验证和本地提交；不推送。

## Safety

- 不读目标标注作为检测输入。
- 不降低原注册/特征质量门。
- 恢复结果独立记录 `sourceDetector/recoveryPass/quality`。
- 外置图片、JSONL、汇总和日志不进 Git。

## Implemented components

- 注册：`no_valid_candidate` 后的 `stable_multi_support`。
- `Φ12.2`：`expanded_radius`、`center_recenter` 和极性/RANSAC
  `robust_multicircle`。
- 尺寸7：单带失败后的 `multi_parallel_bands`，以及原v6质量回退。
- 几何一致性：只从旧参考标注几何导出比例，只诊断/粗错边拒绝，
  `outputAdjustmentApplied=false`。
- 圆弧补全：读取外置 LabelMe 可见弧，复用 Kasa 初值、稳健/几何拟圆；用源点中位间距推导完整圆点数并输出外置审阅包。
- 补全质量：至少8点、有限坐标、中位径向残差 `<25 px`、可见弧覆盖 `>=120°`；自动结果不是真值。
