# Research: A2多槽候选角色几何与真实数据验收

## R0 — 现场图纸视频纠正双缺口业务假设

**Decision**: 以通用多候选和显式datum/target角色分配为主模型；paired仅作兼容诊断。

**Rationale**: SHA-256为`39f1029b9ea014f59b2286d49ed2d0172d750c125be9bfc6ba4518b753bec17e`的视频是图纸讲解，
只显示竖向基准、左槽射线和`85°±5° (Z106)`，不证明A2顶部双缺口就是datum/target。

**Alternatives considered**: 继续以双缺口中线为默认真值（拒绝）；从候选数自动推断角色（拒绝）。

## R0a — 分离图纸夹角、公差判定与机械纠偏

**Decision**: 诊断同时输出顺时针有向角和最小夹角；公差用途未确认时为`NOT_EVALUATED`，正式纠偏角为空。

**Rationale**: 85°±5°可能是尺寸验收，也可能是引导换算几何输入，两者单位相同但业务契约不同。

**Alternatives considered**: 将夹角直接写入v2正式姿态字段（拒绝）。

## R1 — 与历史A端面链的复用边界

**Decision**: 保留`estimate_global_transform`用于圆心/尺度和旧诊断，保留`estimate_rotation_by_polar`作一致性信号；
多候选只在已有外圆环带上调用`polar_resample`并分析角度剖面。

**Rationale**: 这是解决旧函数只返回最长暗区、无法显示次候选的最小补丁，不重复已验证的圆/配准/极坐标算法。

**Alternatives considered**: 修改只读历史源、复制其整套函数、新建OpenCV检测链；均违反边界或造成双实现漂移，拒绝。

## R2 — 环形剖面与全候选提取

**Decision**: 外圆内侧固定像素宽度的环带由历史`polar_resample`采样，径向均值形成角度剖面；使用环形移动平均、
中位数/MAD暗区阈值和环形连通段枚举，对每段用亮度亏损加权计算中心。

**Rationale**: 与历史notch定义保持同源，同时正确处理角度端点相邻和全暗区列表。

**Alternatives considered**: 直接切图做连通域或边缘直线拟合；增加新坐标与形态语义，且无A2证据支持，拒绝。

## R3 — 裁切与无效环带

**Decision**: 采样前使用圆心、环带外半径和图像边界检查整圆入镜，并对圆心、尺度的有限性和配置范围单独验证。

**Rationale**: 历史`polar_resample`对越界样本有填充语义，不能用填充值伪造完整环带和候选唯一性。

**Alternatives considered**: 容许部分可见弧并推断配对；对机械引导风险过高，首版拒绝。

## R4 — 双缺口配对与唯一性

**Decision**: 枚举候选两两组合，按最短环形角间距、单侧宽度/显著度范围、宽度比和显著度比先硬门控；
通过者按间距接近期望中心、宽度对称和显著度对称组合得分。最佳得分与次佳差距均达标才唯一。

**Rationale**: 硬门控使失败原因可解释，次优差距直接表达配对歧义；确定性排序保证重复运行稳定。

**Alternatives considered**: 只取两个最显著候选，或一旦有两个就配对；无法拒绝额外暗区和等价配对，拒绝。

## R5 — paired旋转与polar一致性

**Decision**: 参考图和目标图均必须有唯一配对；两中心线角的环形差作paired rotation，与现有polar rotation比较。

**Rationale**: 绝对候选方位用于诊断，相对参考旋转用于验证单图稳定性；两条链差异过大时fail-closed。

**Alternatives considered**: 继续使用旧`transform.rotation_deg`作正式角；已有A2摸底出现大幅跳变，拒绝。

## R6 — 诊断模式与生产语义

**Decision**: 配置分开`diagnostic_mode`、`target_semantics_confirmed`和现有`conventions_confirmed`。旧配置缺少目标语义字段时按未确认处理。

**Rationale**: “检出什么”和“怎样映射到机械角”是两个独立外部决策；默认失败对旧调用者更安全。

**Alternatives considered**: 选择paired即视为语义确认，或沿用`conventions_confirmed`代表两个决策；会把技术模式冒充业务确认，拒绝。

## R7 — v2兼容性

**Decision**: 不升结果Schema；新字段只进`diagnostics.angularProfile`、`diagnostics.candidates`、`diagnostics.pairing`和
`diagnostics.diagnosticMode`，旧顶层及`result/error`不变。

**Rationale**: 现有Schema已允许`diagnostics`为开放对象，旧消费者可忽略新键；没有不兼容证据。

**Alternatives considered**: 升为result/3；对纯诊断增量会无谓地迫使下游迁移，拒绝。

## R8 — A2分组、truth和统计

**Decision**: Manifest记录显式的dataset class、sample/condition/repeat/split和可选capture timestamp/sequence；truth通过SHA-256关联。
同条件使用环形展开后的角范围，跨真值条件使用环形误差组均的极差/标准差；正常/坏图分报告。

**Rationale**: 文件数不证明采集组；原始角度在不同真值组天然不同，只有残差可比；坏图的核心指标是误引导而非角误差。

**Alternatives considered**: 按500/20自动分25组、对原始角组均求极差、将失败填0；均会制造伪统计，拒绝。

## R9 — 暗区与真实凹槽分层

**Decision**: 原始环形暗区仅作高召回候选；在更深的内侧polar环带上，以外缘连通径向深度、候选两侧局部金属对比、成对边缘支持、宽度变化和中心漂移评估真实凹槽。先过硬门，组合分只用于表达证据强度和临界歧义。

**Rationale**: 真实开口槽应在单帧中表现为从标称外缘向内的局部凹入且有两侧边缘；阴影或工装边界可以很暗、很稳定，但往往缺少对称边缘或具有扇形宽度/中心漂移。这些证据可追溯、不需要训练数据并可单帧部署。

**Alternatives considered**: 按候选排名或固定角度选择（过拟合，拒绝）；依赖跨帧移动性（生产单帧不可用，拒绝）；直接训练分类器（无冻结标签且违反传统几何优先，拒绝）。
