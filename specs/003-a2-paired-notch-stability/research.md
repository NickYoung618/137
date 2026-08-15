# Research: A2多槽候选角色几何与真实数据验收

## R0 — 现场图纸视频纠正双缺口业务假设

**Decision**: 以通用多候选和显式datum/target角色分配为主模型；paired仅作兼容诊断。

**Rationale**: SHA-256为`39f1029b9ea014f59b2286d49ed2d0172d750c125be9bfc6ba4518b753bec17e`的视频是图纸讲解，
只显示竖向基准、左槽射线和`85°±5° (Z106)`，不证明A2顶部双缺口就是datum/target。

**Alternatives considered**: 继续以双缺口中线为默认真值（拒绝）；从候选数自动推断角色（拒绝）。

## R0a — 分离图纸夹角、公差判定与机械纠偏

**Decision**: 诊断同时输出顺时针有向角和最小夹角；公差用途未确认时为`NOT_EVALUATED`，正式纠偏角为空。

**Status update (2026-08-15)**: 该决策保留为v1兼容背景；公差用途和图像纠偏方向现已由R13/R14确认，PLC权限仍未确认。

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

## R10 — 复用gyj物理外圆检测核心

**Decision**: `multi_notch_roles`直接调用指纹锁定历史源中的`outer_boundary_edge_point`与
`robust_fit_circle`；本仓库不再保留平行的外缘灰度阈值算法，只负责720射线编排和更严格的fail-closed质量门。

**Rationale**: gyj实现已包含双线性径向采样、外部暗背景上下文、最外层亮到暗交点、亚像素抛物线峰值和MAD离群点剔除。直接复用可避免两套外圆语义和阈值漂移。

**Alternatives considered**: 保留本仓库独立polar阈值外圆并与gyj投票（两个相关算法不能构成truth，且增加漂移，拒绝）；将单帧算法结果当作精度truth（循环验证，拒绝）。

## R11 — 人工开放槽边界只作离线审阅

**Decision**: 人工外圆弧和开放槽边界由独立CLI读取，标签映射显式传入；圆拟合直接调用锁定gyj
`fit_circle`和`robust_fit_circle`（内部调用`geometric_circle_fit`），运行时适配器不导入该工具。

**Rationale**: 人工边界可以回答“哪段轮廓是真槽”并验证槽口中点数学，但若作为检测输入会产生真值泄漏。
开放边界的两端靠圆、内部径向内凹、最深点位置和折线连续性可拒绝非凹入阴影样式；单个样本仍不能
证明所有遮挡类型或生产准确率。

**Alternatives considered**: 把label2直接送入运行时角色分配（真值泄漏，拒绝）；复制孔2拟圆代码
（双实现漂移，拒绝）；将右上实测21.87°改写为左下85°（伪造目标，拒绝）。

## R12 — 单真实槽与机械引导分层

**Decision**: 新增显式`single_real_groove`。它与multi-role共用物理外圆、原始暗区和单帧几何门，
但以恰好1个接受候选为图像槽姿态成功，不执行datum/target双角色排列；0个失败，多于1个歧义。

**Status update (2026-08-15)**: “datum未确认”只描述v1阶段；R13/R14已确认Y下半轴datum和目标评估，同时继续保留PLC权限分层。

**Rationale**: 现场已确认每件只有一个真实槽，另外两个外观暗区是遮挡阴影。旧模式把接受数1与
配置角色数2比较，错误地将已经成功的凹槽识别报告为`GROOVE_RECOGNITION_FAILED`。图像绝对方位
可以独立成立，但85°是相对未确认datum的量，不能从单槽绝对方位直接相减。

**Alternatives considered**: 把multi-role最少角色数改成1（会破坏图纸角色兼容语义，拒绝）；按检测到的
候选数自动切换模式（隐式业务推断，拒绝）；把图像绝对方位直接写入正式机械角（datum缺失，拒绝）。

## R13 — Y轴下半轴的有向单槽角

**Decision**: 以物理外圆圆心为原点，图像向右为`+X`、向下为`+Y`；从向下`+Y`半轴到槽口中点径向线的最短有向角为实测角，顺时针正。槽口中点不使用亮度加权中心；R16实施后，粗候选边界只作搜索初值，最终中点固定来自亚像素侧壁—外圆交点。

**Rationale**: `atan2(-dx,dy)`在图像坐标中直接给出该角；左下目标为正角，右下镜像为负角。位置硬门`dx<0,dy>=0`与角度门`[80°,90°]`双重约束，可避免将右下无向85°或左上暗区判为合格。

**Alternatives considered**: 只取无向夹角（会接受右下镜像，拒绝）；只写“二/三象限”（图像Y轴向下导致编号歧义，拒绝）；用暗区加权中心代替槽口两边中点（光照可引入偏移，拒绝）。

## R14 — 目标评估与PLC权限分层

**Decision**: 单槽v2诊断输出实测角、`+85°±5°`公差状态、有向偏差和图像坐标系纠偏建议。`mechanicalCorrectionDeg`与顶层`result.signedRelativeRotationDeg`只在独立PLC映射门确认后允许填充；本轮不写PLC。

**Rationale**: 现场已确认图像角的datum、目标、公差和方向，因此继续将公差状态设为`NOT_EVALUATED`会丢失已确认业务语义。但PLC地址、缩放、字节序和握手未确认，图像纠偏不能被下游误解为已编码控制命令。

**Alternatives considered**: 继续全部`NOT_EVALUATED`（不反映新权威需求，拒绝）；立即填顶层角或写PLC（越过B-005，拒绝）；静默改变v1配置语义（兼容风险，拒绝）。

## R15 — 人工圆弧是拟合参考，不是运行时常量

**Decision**: 先用锁定gyj `fit_circle` → `robust_fit_circle`（内部`geometric_circle_fit`）把人工
可见圆弧变为参考圆候选，再同图比较自动物理圆。对照分开报告圆心向量/距离、半径差、归一化差、
圆心误差的角度影响上界，以及人工槽边界中点与自动槽口中点的环形差。

**Rationale**: 人工描线擅长确认“哪条边才是工件外圆”，长弧多点拟合还能平均点击噪声；自动算法
擅长可部署的亚像素边缘定位。二者同图对照比把任一方当作绝对正确更可靠。当前134点、约236°覆盖
的样本是很好的开发参考，但单人单样本尚不能证明生产准确率。

**Alternatives considered**: 把该圆心固定套到后续零件（工件平移时失效，拒绝）；生产读取LabelMe
（真值泄漏，拒绝）；用同一批图调参又验收（数据泄漏，拒绝）；仅比较半径而不比较圆心和最终槽角
（无法定位误差来源，拒绝）。

## R16 — 粗候选之后做槽侧壁亚像素精修

**Decision**: 现有环形暗区剖面继续负责高召回候选和真假槽几何门。唯一真实槽通过后，在粗左右边界
附近沿多个径向层进行密集双线性采样，以连续阈值/梯度插值得到亚像素侧壁点，分别稳健拟合两条直线，
再与robust/geometric外圆求邻近粗边界的唯一交点。最终业务角使用两个圆交点的环形中点。

**Rationale**: 当前1440角采样仍是0.25°栅格，在半径1646 px处相当于约7.18 px圆周步长，不足以把
`1 px≈0.0348°`的理论分辨率兑现为算法输出。局部高密采样加侧壁线拟合能利用多行证据并把交点落实
到连续坐标；外圆仍完整复用gyj的亚像素边缘与稳健几何拟圆。

**Alternatives considered**: 直接把粗候选`startDeg/endDeg`当最终角（量化误差，拒绝）；仅增加全圆
角采样数（耗时高且没有侧壁/交点残差门，拒绝）；把人工槽线送入运行时（真值泄漏，拒绝）；只凭
`1/r`公式宣称生产精度（忽略圆心、侧壁、畸变和重复性误差，拒绝）。
