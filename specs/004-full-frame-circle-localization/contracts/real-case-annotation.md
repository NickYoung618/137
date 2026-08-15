# Contract: Real-case LabelMe Annotation and Comparison v1

## Purpose

每个进入真实效果验收的图像必须绑定独立人工标注，使审阅者能够同屏看到“应该在哪里”和“算法检测在哪里”。无标注样本仍可运行无真值诊断，但不得进入准确率分母。

## LabelMe shapes

每个已复核JSON必须包含：

1. 物理外圆二选一：
   - `label=physical_outer_circle_truth`、`shape_type=circle`、两点；或
   - `label=physical_outer_circle_visible_arc_manual`、`shape_type=linestrip`、至少8个有限点并通过圆拟合残差和可见弧覆盖门。
2. `label=target_groove_open_boundary_manual`、`shape_type=linestrip`、至少6个有限点；首尾点为槽口两端，折线连续、向圆内凹入且端点靠近人工圆。

点数是最小质量要求，不是固定77、134或34点契约。

根级flags必须包含：

```json
{
  "human_verified": true,
  "independent_from_algorithm": true,
  "formal_truth": true,
  "runtime_input_allowed": false,
  "annotation_version": "reviewed-v1",
  "annotator": "operator-id",
  "reviewer": "different-reviewer-id"
}
```

若存在算法预标，只能使用`algorithm_suggestion_*`标签并保持`formal_truth=false`；它不得与人工truth共用标签或自动转正。

## Annotation index

外置索引逐图记录：安全相对图像路径、图像SHA-256、安全相对LabelMe路径、标注SHA-256、版本、标注员、独立复核员、复核状态、split和拒绝原因。标注员与复核员必须不同。

严格验收要求：

- 每个Manifest图像恰好匹配一条索引；
- 图像与标注哈希一致；
- `reviewStatus=reviewed`；
- `humanVerified=true`且`independentFromAlgorithm=true`；
- shape和几何质量全部通过。

任一条件失败，命令返回非零，样本比较值为`null`并给出原因。

## Per-image comparison

逐图JSON/CSV至少包含：

- 人工圆心、半径；自动圆心、半径；`dx`、`dy`、圆心距离、半径有符号/绝对差；
- 人工槽开口两端、圆周中点、相对Y下半轴有符号角和象限；
- 自动亚像素槽口两端、中点、同一角度和象限；
- 环形槽角差、人工/自动85度正负5度状态；
- 检测错误码、标注错误码、`evaluationEligible`及不可评估原因。

报告还必须按Manifest中显式的`sampleId + position + conditionId + split`分组计算静态重复性。组内使用检测角减人工角的环形残差，报告展开后的极差、标准差和P95绝对偏差。`groupingExplicit=false`、有效重复数不足或人工truth缺失时只能输出`NOT_EVALUATED`，不得把不同角度组的原始角度混成“动态极差”。

叠加图颜色必须固定并有图例：人工外圆/槽、自动外圆/槽、人工径向轴、自动径向轴可区分。不得只画检测结果而隐藏标注。

## Current dataset status

当前25张JPEG均没有与JPEG哈希严格绑定的已复核同图truth。第4帧只有一张同源原始BMP的精细人工圆弧/开放槽边界开发参考，不能自动转正为JPEG truth。25张均生成`template`索引和空白LabelMe待办；在人工完成和独立复核前，004真实批跑只报告检测稳定性，不报告25张准确率。
