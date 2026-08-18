# Contract: 物理外圆边族选择

## Configuration

`detector.physical_outer_circle.edge_family_selection`是严格校验、默认关闭的嵌套对象。

必须字段：

- `schema_version = physical-circle-edge-family-selection/1`
- `enabled: boolean`
- `strategy_version: non-empty string`
- 有界多峰参数：最大峰数、最小梯度、最小径向分离。
- 有界搜索参数：最大种子数、最大假设/族数、固定迭代数。
- 预选参数：每射线归属残差、最小支持、最小角覆盖、最大预选残差。
- 同族去重参数：最大中心/半径差与最小支持重叠。

所有数值必须有限且范围有序。功能关闭时不得要求新多峰原语存在；功能开启但运行时模块缺少原语时必须在配置/初始化阶段明确拒绝。

## Runtime Input/Output

输入：灰度图、搜索圆、原有对齐圆、原有物理圆配置、共享多峰原语和已有鲁棒拟圆。

处理契约：

1. 每条射线最多采样一次并保留有界候选。
2. 每族每射线最多贡献一个真实观测；缺失不补点。
3. 候选重排、ID改名和整数射线循环旋转不得改变族数量、圆或失败类型。
4. 同族多种子去重后，合格族数量必须严格等于1。
5. 仅唯一赢家调用已有鲁棒拟圆，随后执行全部原物理圆质量门。

成功：`edgeFamilySelection.status=selected`且`selectedFamilyId`非null；最终`physicalCircle`仍须通过原质量门。

失败：

- `no_qualified_edge_family`: 0个合格族。
- `ambiguous_edge_families`: 多个合格族；传播`HOUSING_CIRCLE_AMBIGUOUS`。
- `family_search_overflow`: 有界搜索容量不足；不得截断后继续。
- `invalid_edge_family_evidence`: 非有限或结构非法证据。

以上失败均要求当前角、调整角、方向、PLC和机械执行量为null。

## Diagnostics

运行时只输出有界摘要：射线/峰/缺失/种子/族计数、各族支持/覆盖/残差/圆/失败项、唯一性和分阶段耗时。不得输出人工真值、私有路径或完整逐射线大数组。

完整逐射线证据只由离线工具写到Git工作树外，并通过`manual-circle-edge-family-analysis` Schema。

## Compatibility

- 默认关闭时旧单峰逻辑、旧函数位置参数、旧配置和旧结果字段保持不变。
- full-frame sparse与final、以及直接物理圆路径必须使用相同策略开关。
- 025 v2剖面保持不变；启用功能必须物化新的显式v3剖面与审计身份。
- 不修改坐标/角度、槽壁/同源性、PLC/HMI或双拍兼容契约。
