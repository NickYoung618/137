# SpecKit Analyze: 定义审计结论

**Status**: IMPLEMENTED_SERVER_GATES_PENDING_MAC_REVIEW

## Confirmed root causes

1. **检测失败**：注册、Phi边缘支持或尺寸7两侧边界拟合可能失败；这是图像/候选质量问题。
2. **几何建模与显示错误**：有效结果也可能把局部弧数学外推成完整检测轮廓，并把尺寸7连接线
   误当成两条边界证据；这是契约和可视化问题，调门限无法修复。
3. **尺寸7成像语义误判风险**：黑色轮廓带的两次梯度跃迁不是两条零件边，而是同一物理边的
   有限宽成像响应；取外峰会系统性扩大尺寸。实现保留transition pairs并拟合其中点轨迹。
4. **验收覆盖不足**：现有Phi单图验收只比较拟合圆参数；现有7标注只比较尺寸线，无法验收两条
   物理边界的拟合位置。

## Decision

- 数值测量几何与可视证据几何必须分离。
- Phi只用旧参考中有LabelMe亚像素相位定义的一侧决定数值圆；另一侧独立检测并审计共同圆
  一致性。没有右侧参考真值时不得机械镜像相位后强行共同拟合。
- 默认交付不得出现完整Phi圆；只能显示实际支持的左右局部弧segments。
- 尺寸7使用下方窄颈两条平行边的垂距；必须显示两条边界线，测量连接线是第三个辅助对象。
- 尺寸7最终A/B边界取各自光学transition pair的中点轨迹；两次跃迁本身完整保留为raw evidence。
- 已实现证据契约和renderer且未调整门限；当前不提交、不push，等待用户复核。

## Acceptance design after clarification

- Phi evidence：预测原始内点到人工可见弧的距离、人工弧角域覆盖、错误物理边极性拒绝；
- Phi model/value：圆残差、直径误差，作为独立指标；
- D7 evidence：两条预测边界分别到人工boundary A/B的距离、平行度和观测长度；
- D7 value：两条边界沿确认尺寸方向的交点距离误差；
- rendering：LabelMe不得包含`shape_type=circle`的Phi预测，必须包含局部`linestrip`；有效7必须
  含A、B两条边界及独立dimension辅助线。

## Root-cause separation after drawing confirmation

- “完整圆/单线画法错误”是确定性契约缺陷，所有数值有效帧都受影响，应先修。
- “部分帧检测不了”仍是候选证据不足问题，必须在左右弧和两条直边证据可见后重新分类；现在
  调门限会掩盖究竟是哪一侧、哪个角域或哪条边失败。

## Implementation verification

- 最新唯一真值单图：PASS；方向270，尺寸7长度误差`0.5684097263 px`，Phi直径误差
  `0.1053051052 px`。检测入口未读取目标标注，标注仅由离线evaluate步骤读取。
- 同图证据：Phi输出`reference_left`与`reference_right`两个实际`linestrip`；D7两边各保留31组
  transition pairs，拟合共享方向的A/B平行有限线，尺寸线为严格公法线。
- 9帧外置诊断：execution error 0；相对当前015基线所有registration/D7/Phi有效状态不变。
  500/521/620控制帧仍为`True/True/True`，501仍为`True/True/True`；520和623的既有Phi失败
  未被伪恢复。
- renderer真实小样人工查看：有效帧只显示局部绿色弧、A/B边界和青色尺寸线；失败帧保留红色
  状态且不外推轮廓。
- 全套`unittest`：140项通过；`compileall`、Schema解析、SpecKit prerequisites、
  `git diff --check`通过。仓库未产生图片、JSONL或运行输出。

## SpecKit consistency analyze

- spec中的三层对象分别映射到contract的`rawEdgeEvidence`、`fittedGeometry`、
  `measurementAnnotation`，实现和两个renderer字段一致。
- 未修改配置和质量门；未新增目标真值运行时角色；未出现12.2、7、310、541.13或哈希特判。
- 唯一未闭环项是Mac视觉/全量回归与证据级双弧、双边人工标注验收，因此不得从服务器样本
  声称2000张正常组或静态重复性达标。
