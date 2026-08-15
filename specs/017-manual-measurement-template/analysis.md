# Analysis: 唯一人工参考迁移

## 架构审计

- 检测API、CLI、batch和shell现只接受一对权威参考JSON/BMP。
- `runtimeInputs`只含`authoritative_reference_annotation`、`authoritative_reference_image`、
  `target_image`和`configuration`。
- 注册使用权威新BMP自身的分布式梯度/纹理支撑；Phi/D7只使用权威新JSON定义几何语义。
- 退役资产没有参数位、坐标变换、fallback或隐式路径；负向测试证明其SHA无法通过唯一参考加载门。

## 质量策略

本增量没有改动配置中的支持数、覆盖、残差、尺度、角度、Phi和D7检边门。新增的图像强度
相关/梯度方向支持是候选排序证据；已知固定工位只搜索0°附近小角度，避免重复圆形结构的正交假匹配。

## 验证边界

权威同图self-check能验证运行时没有第二套参考、单位变换、测量检边和离线精度契约；它不能证明
2000张normal泛化达标。服务器9帧只有状态真实性，无目标真值，因此只报告执行/注册/测量状态，不宣称精度。

## 最终验证

- 权威同图self-check：`templateSelfCheck=true`，注册方向0°，变换`dx=0, dy=0,
  scale=1, theta=0`；D7长度误差`0.5461624607 px`，Phi直径误差`0.9394610606 px`，PASS。
  该结果只证明自检契约，不是多样本泛化证据。
- 9帧外置诊断：execution error `0/9`，registration `9/9`，Phi `9/9`，D7 `7/9`。
  500/521/620三帧控制帧均为注册/D7/Phi有效；501和520的D7明确为
  `tangent_boundary_fit_failed`，未伪造有效。该集无批量真值，不作精度声明。
- 全套`unittest discover -s tests -q`：147项通过。
- `compileall`通过；12个JSON Schema通过Draft 2020-12结构检查，真实E2E结果通过result v2验证。
- SpecKit prerequisites明确解析到017；spec/plan/tasks/research/contracts/quickstart与实现字段一致。

## SpecKit analyze结论

- FR-001/FR-007映射到run/batch/shell的单参考参数及四角色provenance测试。
- FR-002映射到冻结SHA、shape结构、缺失/篡改/退役资产拒绝测试。
- FR-003/FR-004映射到新BMP像素支撑、ROI粗匹配、候选图像一致性诊断及原质量门。
- FR-005/FR-006/FR-009映射到Phi/D7新参考检边、质量状态和016证据分层/可视化测试。
- FR-008映射到self-check单位变换、`authoritativeReference`与result/provenance/acceptance Schema。
- 未发现缺失需求、相互冲突门或目标真值运行时泄漏。
