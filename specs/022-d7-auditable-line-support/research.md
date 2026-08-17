# Research: D7可审核直边支持

## 1. Evidence audit

### 1.1 Geometry is linear, not curved

当前581和582的正式A/B使用共同法向的两条平行直线。服务器结果显示：

| frame | A/B显示段长度(px) | shared line normal | D7(px) |
|---|---|---|---:|
| 581 | 72.899 / 66.129 | `[-0.035302,-0.999377]` | 303.774349 |
| 582 | 71.887 / 61.573 | `[-0.044433,-0.999012]` | 303.842993 |

`segmentPointsPx`只是同一直线上的两个端点，renderer调用Pillow直线绘制，没有曲线插值。用户看到的“不像直线”
主要来自短段、交界纹理、缩放抗锯齿和缺少足够的直边上下文，而不是拟合对象变成了圆弧。

### 1.2 Support span is artificially local

`_paired_contour_boundary()`只在D7公法线端点附近沿边界切向扫描固定`±36px`，31条剖面。
随后`_shared_parallel_boundary_geometry()`用这些点的最小/最大切向投影生成显示段，所以最大可见跨度天然约72px。

581/582外置人工D7-A/B线各约390--421px，只用来证明照片中确实存在明显更长的物理直边；它们不得作为
运行时端点或长度目标。当前约61--73px审核段不足以直观判断拟合线是否贴合窄颈。

### 1.3 Current span mixes two physical directions

现有扫描在公法线两侧对称展开：一半朝窄颈直段，一半朝圆柱/连接圆角。即使圆柱侧点偶然接近拟合直线，
也不应把该区域显示为“窄颈实际直边”。正确显示范围应从公法线附近向远离Phi圆心的窄颈方向收集，
并在同语义paired-transition支持停止处结束。

### 1.4 v6 evidence is computed but discarded

v6 `detect_dimension_boundary()`已有可选diagnostics，能提供raw points、inlier points、直线方程和支持段；
`d7_dual_boundary_values()`调用时未传diagnostics，因此这些证据未进入`Extraction.measurements`。
current-capture fallback随后又显式删除新式边界证据，使010只剩两个交点和长度。

v6检测的是单个参考极性梯度层；正式current-capture物理语义是有限宽暗轮廓带的两次相反梯度中点。
所以即使补回v6真实点线，它也只能是review-only，不能使`evidenceComplete=true`。

## 2. Decisions

### Decision A: Preserve measurement geometry and values

正式D7线方程、公法线交点、数值和质量状态保持不变。本轮只扩充/裁剪可视证据范围。

**Rationale**: 用户问题首先是可审核性；现有100帧状态和权威真值已验收，不能用显示问题触发数值调参。

**Alternative rejected**: 重新拟合扩展点并改写D7。它可能改善视觉，但会把证据显示增量变成未验证的测量算法升级。

### Decision B: Do not extend with a different optical-edge semantic

初版尝试在现有band offsets继续收集paired支持。581/582显示A侧只能稳定到约48--72px偏移，B侧在24px后
就没有足够同语义支持；单梯度路径虽可画得更长，但在合成暗边上落到光学边带一侧，与paired中点相差4px，
被现有3px残差门正确拒绝。Spec 019/020也已证明单梯度可能选择约317px错误层。

**Final decision**: 不把单梯度或远处非同语义点用于正式显示范围。正式A/B只保留当前已验收paired点中从公法线
朝窄颈方向的部分，并将这些点投影到冻结直线。线段短是证据范围结论，不是用外推掩盖的问题。

**Alternatives rejected**: 延长到图片边缘、人工LabelMe端点、或用单梯度层撑长；三者都会制造无同语义证据的轮廓。

### Decision C: Clip display to outward, supported projections

显示段端点由合格支持点在既有直线上的投影范围生成，且只保留公法线向窄颈方向的连续支持。
不把圆柱侧对称扫描点纳入显示范围。

### Decision E: Use a zoomed audit inset instead of unsupported extrapolation

批量预览左下增加D7局部放大，明确标出A、B和公法线。局部放大只重新采样原图和既有坐标，LabelMe仍保持
3072x2048原坐标；它解决全图缩放下短直线“不像直线”的可见性问题，不把整段窄颈冒充为已检测轮廓。

### Decision D: Replay v6 evidence in the adapter as a separate review layer

冻结核心不能修改。适配层使用v6 `Extraction`最终变换、同一目标图、同一参考极性和现成
`detect_dimension_boundary()`默认参数确定性重放两侧检测；只有重放交点与v6正式交点在数值容差内一致时，
才把diagnostics写入独立`legacyReviewBoundaries`。renderer/LabelMe使用REVIEW标签和不同颜色。
正式`rawEdgeEvidence.boundaries`及`fittedGeometry.boundaries`保持空，证据状态继续`unavailable`。

**Rationale**: 同时满足“看到旧路径实际选择的层”和“不伪造成同语义物理边界”。

**Alternative rejected**: 修改`algorithms/hole_2/main.py`让核心直接输出diagnostics。Constitution要求冻结复用核心字节不变；
适配层可用同一公开检测函数安全重放而不修改核心。

## 3. Risk controls

- 支持裁剪和局部放大不参与候选评分、D7数值或valid判定。
- `algorithms/hole_2/main.py`保持字节不变；提交前记录SHA并审计。
- 不修改配置或门；正式显示范围只使用既有通过的paired点云。
- Phi路径不调用任何新D7证据函数。
- 100帧比较必须逐帧核对registration/D7/Phi状态和数值，而不只比较汇总计数。
- 581/582人工线只用于离线可视对照，不进入运行时。
