# Analysis: D7失败证据与Phi实线拟合圆审核

## Frozen baseline

- repository/branch: `137壳体检测-孔2柱面和端面检测` / `main`
- HEAD and `origin/main`: `c9399dadeaa4073d30f5ce134430e579f001c803`
- worktree at start: clean
- Mac baseline: execution `9/9`, registration `9/9`, Phi `9/9`, D7 `7/9`；501和520为
  `tangent_boundary_fit_failed`。

## Analysis method

先在原基线重跑外置9帧，不改运行时算法。对501/520读取结果中每个扫描带、每侧候选、拟合
残差、轴方向一致性、边缘峰值、跨带聚合与fallback证据，并与500/521/620控制帧及原图ROI对照。
只有多项独立证据支持真实边界且所有原质量门均通过时才允许恢复；否则保持明确失败。

## Baseline rerun

- 服务器外置9帧基线重跑：execution `9/9`、registration `9/9`、Phi `9/9`、D7 `7/9`。
- 失败仅501、520，均为`tangent_boundary_fit_failed`；500、521、620控制帧全部有效。
- Mac反馈将520写作`215536_520`；服务器实际外置文件名为`Pic_2026_08_12_215537_520.bmp`，
  本分析按共同帧号520和服务器真实文件执行。
- 501和520注册变换相同（`scale=1.0082621`、`theta=-1.72137°`），Phi均有效，故失败发生在
  D7局部边界检测，不是执行、注册或Phi上游清空。

## 501逐阶段证据

### current-capture paired-transition primary

- 失败侧：`p1`，即D7上侧/A边界；`p2`下侧/B边界通过。
- p1有20组transition pair及20个拟合内点，内/外峰中位数`7.353/7.633`均高于峰值门`4`，
  但直线残差中位数`12.305 px`，超过原门`3 px`；失败阶段为`fit_residual_above_gate`。
- p1轴对齐余弦`0.8879`高于原门`cos(35°)=0.8192`，所以根因不是点数、峰值或轴门，
  而是这些高于峰门的点没有组成同一条直边。
- p2有31组pair、25内点，残差`0.537 px`、轴余弦`0.9992`，两侧峰`22.684/14.205`，
  是稳定有效的下边界。

### multiband recovery

- 7条带没有一条能让两侧同时有效，paired valid count为`0`。
- p1只在offset `0/24 px`得到两个单侧候选，轴偏移分别`7.624/1.063 px`；数量`2<3`，
  最终失败为`p1_bands_below_gate`。其余p1条带分别为点集拟合失败、轴方向失败或残差
  `3.236/4.315 px > 3 px`。
- p2也只有offset `48/72 px`两个有效单侧候选；其他条带主要被轴方向门拒绝。因此即使跳过
  p1的先行失败，也没有两侧各至少3条一致证据。

### v6 fallback

原v6质量为`failed:p2_boundary_fit`：其第一端点仅13点、残差`2.558 px`、峰`6.028`，第二端点
无合格拟合。注意v6自身端点命名/搜索坐标与current-capture的p1/A语义不是同一诊断对象；
两条路径都没有同时给出两条合格边界，故`v6_original_quality_rejected`正确阻止fallback。

## 520逐阶段证据

### current-capture paired-transition primary

- 失败侧同样为`p1/A`；20组pair中有19个内点，峰`6.817/7.214`高于门，但轴对齐余弦
  `0.7213 < 0.8192`，失败阶段为`axis_alignment_below_gate`，因此残差阶段未被采信。
- p2有31组pair、26内点，残差`0.548 px`、轴余弦`0.9991`、峰`21.987/14.044`，稳定通过。

### multiband recovery

- 7条带paired valid count仍为`0`。p1有3个单侧候选，轴偏移`0.554/6.660/3.236 px`；
  以中位数`3.236 px`和原一致性门`3 px`计算只有2个内点，故`p1_consistency_below_gate`。
- p2仍只有offset `48/72 px`两个有效候选；其他条带为点集拟合或轴方向失败。即使接受p1，
  p2数量仍小于最小一致带数3。

### v6 fallback

原v6同样为`failed:p2_boundary_fit`；其第一端点12点、残差`0.856 px`、峰`6.079`，第二端点
没有合格拟合，所以原质量门不允许fallback。

## Image evidence and D7 decision

仓库外ROI/点云叠加显示：501/520的红色p1候选散落在上侧圆弧连接、加工纹理和污点上，
拟合出的短段方向互不一致；蓝色p2点和primary p2线则贴合下侧真实暗边。620控制帧的p1/p2
点云都沿两条实际轮廓连续分布，3个中间条带同时有效且长度偏差仅`0.332 px`。

因此501/520缺少“两侧各至少3条一致直边”这一必要图像证据。降低最小带数、轴余弦或残差门
都会把纹理/弧形过渡当直边，本增量不修改D7算法和门限，两帧继续明确失败。失败帧不显示正式
A/B或公法线是因为没有通过质量门的`fittedGeometry`，不是renderer漏画；诊断点云只能作为
拒绝原因审核层，不能伪装成有效测量线。

## Display decision

Phi局部弧与拟合圆属于不同证据层。绿色局部弧继续表示真实命中边缘；蓝色完整圆改为连续实线，
但LabelMe仍标记`fittedModel=true`、`isDetectedContour=false`。实线圆直接读取与数值测量相同的
`fittedGeometry.centerPx/radiusPx`，不增加第二套渲染拟合或补偿。

## Display verification

- 单批报告和old/new对照报告都通过统一helper以一次`ellipse`调用绘制完整圆，不再分段调用`arc`。
- 501、520、620的LabelMe `fit-circle`第一点逐值等于`fittedGeometry.centerPx`，第二点逐值等于
  `[centerX + radiusPx, centerY]`；三帧均为`fittedModel=true/isDetectedContour=false`且各保留1条
  绿色`reference_left`局部弧。
- 620有效帧同时输出`boundary:A`、`boundary:B`和`dimension`；501/520因D7无有效拟合几何，
  正式LabelMe不输出D7线。其仓库外诊断叠加仍保留被拒候选点，便于核查失败原因。
- 人工查看三张外置预览：蓝色实线圆连续显示，绿色弧与拟合圆在实际支持角域贴合；未观测角域
  的蓝线只是拟合外推，显示差异正是审核用途，没有另加坐标或半径补偿。

## Final verification

- 权威同图：单位注册，D7长度绝对误差`0.5461624607 px ≤ 2 px`，Phi直径绝对误差
  `0.9394610606 px ≤ 1 px`，PASS。
- 修改后9帧：execution `9/9`、registration `9/9`、Phi `9/9`、D7 `7/9`；501仍为
  `p1_bands_below_gate`，520仍为`p1_consistency_below_gate`，无新增回归或伪恢复。
- 全套unittest `149/149`通过；compileall通过；24个Draft 2020-12 JSON Schema通过。
- SpecKit prerequisites解析到018；`git diff --check`、退役运行时标识扫描、运行产物审计和大文件
  审计通过。`algorithms/`及`config/`无改动，因此检测核心、配置和所有门限保持基线不变。

## SpecKit analyze matrix

| Requirement | Completed evidence |
|---|---|
| FR-001/FR-002 | 501/520逐侧、逐阶段诊断表与ROI审阅 |
| FR-003/FR-005 | 单批/版本对照renderer像素级实线测试及仓库外小样 |
| FR-004 | LabelMe shape/flags/坐标契约测试 |
| FR-006 | D7 A/B/公法线存在与失败不伪造测试 |
| FR-007/FR-008 | config/core diff、holdout路径、Git产物审计 |
| FR-009/FR-010 | 权威同图与9帧真实运行 |
| FR-011 | 工程门禁日志 |

全部FR均有实现或验证映射，未发现遗漏、冲突或未经证据支持的D7恢复。显示样式变化只发生在
两个renderer；数值、有效性、原始证据与拟合模型契约仍彼此分离。
