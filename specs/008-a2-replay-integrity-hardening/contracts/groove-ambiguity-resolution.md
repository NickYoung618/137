# Groove Ambiguity Resolution Contract v1

输入：2..N个已经通过groove recognition的候选、检测图、物理圆、现有refinement配置。

配置：

```json
{
  "schema_version": "single-groove-refinement-resolution/1",
  "enabled": false,
  "max_candidates": 3
}
```

规则：逐候选独立调用同一个槽壁/外圆交点refiner；不使用候选编号、图像绝对角、85°目标、目录class、跨帧运动或粗score选择。恰好一个accepted survivor才输出selected id。所有attempt诊断保留；0、多于1或超限均无角度。

默认关闭，直至独立候选级人工标注验证完成。
