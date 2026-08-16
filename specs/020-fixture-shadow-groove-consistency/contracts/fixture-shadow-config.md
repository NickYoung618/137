# Contract: Fixture Shadow and Source Consistency Configuration

新字段位于detector下，旧配置缺失时按enabled=false。

fixture_shadow_model必须包含：

- schema_version=fixture-shadow-model/1
- enabled=false
- coordinate_frame_id=image-x-right-y-down-clockwise/1
- 两个模板，每个有唯一template_id、有限中心角/漂移、宽度及标量参考
- profile_sample_count为奇数且有硬上限
- intensity_profile和gradient_profile必须同时为空或长度等于profile_sample_count
- max_overlap_hypotheses有1至8的硬上限
- enable_overlap_decomposition=false；参考剖面缺失时不得设为true

sidewall_source_consistency必须包含：

- schema_version=groove-sidewall-source-consistency/1
- enabled=false
- threshold_version
- 最大对比/梯度归一化差、最大剖面MAE、最小相关性、最大径向覆盖差、最大终点结构差
- 所有数值有限且范围明确

约束：

- 两项只允许single_real_groove模式显式启用。
- fixture shadow命中不得删除原始候选。
- source consistency启用时必须使用groove refinement v2。
- 实验配置不得覆盖基础配置文件。
