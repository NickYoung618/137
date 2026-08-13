# Research: A端面槽姿态估计

## R1 — 首版算法路线

**Decision**: 直接复用SHA-256固定的历史A端面传统视觉链，不实现平行替代算法；新增只读适配器将
端面中心、外缘notch和polar旋转输出接入槽姿态契约。

**Rationale**: 服务器没有A2训练数据；几何结构明确、参数可追溯，传统方案最适合快速建立可运行
基线和错误诊断。

**Alternatives considered**: 另写OpenCV圆/极坐标/槽检测、端到端模型。前者重复已有代码，后者缺少
冻结标注集和真实域覆盖，均拒绝。

## R2 — A端面中心定位

**Decision**: 复用`object_bbox_center`、`robust_fit_circle`、`detect_alignment_circle`和
`estimate_global_transform`，适配层只检查中心在图内及尺度合理性。

**Rationale**: 圆中心同时提供平移不变的极坐标原点和槽方位原点；两条独立路径便于失败诊断。

**Alternatives considered**: 固定ROI或另写Hough/轮廓圆。前者不稳，后者重复既有实现，均拒绝。

## R3 — 槽候选检测

**Decision**: 复用`polar_resample`、`find_outer_notch_angle`、`estimate_rotation_by_notch`和
`estimate_rotation_by_polar`。外缘notch方位作为当前槽候选；polar与notch旋转差作为一致性质量。

**Rationale**: 既有实现已将径向外缘缺口在极坐标域形成稳定角度信号，并用notch与polar两条路径
互相校验；适配层无需重复提取。

**Alternatives considered**: 新建角度异常检测或直线检测。均与现成函数重叠，拒绝。

## R4 — 角度与180°歧义

**Decision**: 使用`find_outer_notch_angle`返回的端面中心外向角作为有向槽方位；机械相对角使用配置
零位和方向符号，归一化到`[-180°,180°)`。历史角度以图像x正轴为0，因y向下而随图像顺时针增大。

**Rationale**: 单纯中心线只能给出模180°方向，不能直接形成机械引导角。

**Alternatives considered**: 另拟合槽中心线。现有外缘notch函数已直接给出有向中心角，首版不重复。

## R4a — 现有算法的已知质量缺口

**Decision**: MVP只使用现有可见质量：notch prominence/half-width、polar rotation score、两种旋转
估计差和尺度/中心检查。多候选唯一性作为待A2证据验证的缺口。

**Rationale**: `find_outer_notch_angle`返回单个最长暗区，不暴露第二候选分数；无真实A2不能证明这会
造成误检，也不能合理设计补丁。

**Alternatives considered**: 立即复制函数并添加候选列表。缺少失败证据，违反最小针对性补丁原则。

## R5 — 未确认机械语义

**Decision**: `conventions_confirmed=false`时允许输出诊断候选方位，但正式相对角必须为空并返回
`POSE_CONVENTION_UNCONFIRMED`。

**Rationale**: 满足Constitution的坐标契约和安全失败要求，同时允许服务器继续做算法研发。

**Alternatives considered**: 默认图像x轴零位和逆时针为生产约定。该选择会把测试约定冒充现场事实，
明确拒绝。

## R6 — 服务器数据现状

**Decision**: 不把服务器历史图片认定为A2，只将其作为未知域只读冒烟输入。

**Rationale**: 服务器未发现`A2.rar`；已知一张`a_end_face/reference.bmp`和20张历史A端面BMP，但没有
相机、工位、方向或与Mac A2批次的映射证据。

**Alternatives considered**: 按目录名自动视为A2。缺乏溯源，拒绝。

## R7 — 数据划分与评估

**Decision**: 按物理样品隔离开发/调参/验证/验收，角度误差使用环形差值；静态用同条件20次，动态
用重新装夹/角度组均值；失败单独统计，不填零。

**Rationale**: 防止同一工件纹理或同一原图派生版本泄漏，确保重复性与检测成功率可解释。

**Alternatives considered**: 按图片随机切分。会造成严重数据泄漏，拒绝。

## R8 — 何时引入模型

**Decision**: 只有冻结真实验证集证明传统方案无法满足已确认现场指标，且已完成错误模式分析、标注
规范、数据隔离和算力评审，才启动模型方案。

**Rationale**: 模型是针对证据明确的外观泛化问题，而不是弥补零位、方向或接口不清。

**Alternatives considered**: 首版直接训练。当前无服务器数据、无受控真值，无法形成可信模型。

## External Decisions Kept Blocked

B-001至B-005属于现场业务/机械决策，不能由技术研究“解析”为默认值。它们通过配置确认标志、
验收状态和PLC禁写门禁控制，不阻塞合成MVP，但阻塞生产交付。
