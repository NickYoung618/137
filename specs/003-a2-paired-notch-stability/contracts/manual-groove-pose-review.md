# Manual Open-Groove Pose Review Contract

该契约只用于Git外人工LabelMe开发样本的离线审阅，不是`slot-pose-result/2`运行时输入或机械命令。

输入通过命令行显式指定两个LabelMe `linestrip`标签：

- `circle-label`：物理外圆可见弧，至少8个有限点；
- `groove-label`：真实凹槽开放边界，至少6个有限点，首尾点是槽口与外圆的两个交点。

标签名和点数不是算法常量。工具先验证开放边界连续性，再复用锁定gyj源的`fit_circle`、
`robust_fit_circle`和其内部`geometric_circle_fit`；圆通过后检查槽口两端靠圆、内部径向内凹、
最深点不在端点和槽口角宽。非凹入或不连续轮廓作为阴影/遮挡样式拒绝。

报告`schemaVersion=manual-groove-pose-review/1`，并分离：

- `measurement.schemaVersion=slot-groove-image-angle/1`：图像向上0°、x向右、y向下、顺时针正、范围`[0,360)`；
- `targetAssessment.targetContract.schemaVersion=slot-groove-target/1`：目标角、目标象限、物理datum定义ID和目标角约定ID；
- `targetAssessment.mechanicalCorrectionDeg`：本工具固定为`null`。

物理datum定义ID或目标角约定ID为空时，目标状态必须为`NOT_EVALUATED`，偏差为空。目标左下85°
不得覆盖当前图像实测右上约21.87°。派生语义LabelMe副本、报告和预览必须在Git工作树外；副本
必须标记`runtime_input_allowed=false`、`formal_truth=false`，原始标注不得覆盖。
