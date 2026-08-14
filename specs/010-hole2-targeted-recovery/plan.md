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
