# Feature Specification: 双帧配对槽姿态与可复核预标注

**Feature Branch**: `021-paired-capture-slot-pose`

**Created**: 2026-08-16

**Status**: Draft（实验默认关闭，禁止合入main）

**Input**: 同一物理零件拍摄两次，中间按现场方案旋转；旋转数值、方向和重复误差尚待确认。

## Clarifications

### Session 2026-08-16

- Q: 双拍是否只是未来设想？ → A: 不是；双拍旋转是正式开发方向，只有旋转参数和时序字段未确认。
- Q: 未确认参数时能否输出引导？ → A: 只能输出逐帧候选与非权威匹配诊断，机械/PLC指令必须为空。
- Q: 人工如何复核混合边？ → A: 工具生成精简AUTO_预标注和RAW/SIMPLIFIED联系表，人工不重画已稳定拟合的外圆。
- Q: 调试叠加线过多时如何复核？ → A: part-019 374/369只生成RAW/SIMPLIFIED对照；SIMPLIFIED仅显示019最终两侧壁/端点和020 fixture A/B候选，不显示圆、定位框、非最终raw射线或长诊断文字。
- Q: 橙色fixture标记能否视为阴影边界或身份真值？ → A: 不能。现有020只提供圆周一维暗区start/center/end及模板匹配状态；应显示“Observed dark angular interval / Fixture identity unconfirmed / Pixel boundary unknown”，不得把最近NOT_MATCHED候选冒充fixture或画成实心区域。
- Q: 374/369人工反馈能证明什么？ → A: 只能证明上方方形缺口是真槽所在区域、019命中至少一侧且另一侧跨到右上阴影；这是一条语义负例，不是像素级侧壁、端点或fixture区域真值。
- Q: 能否在该负例上直接放宽020门限？ → A: 不能。新增独立、默认关闭的局部第二侧壁诊断；它枚举同一局部开口内的侧壁假设并保持原020失败状态，只有人工标签和分件验证后才讨论生产选择。
- Q: 双拍和单帧当前哪个优先？ → A: 双拍保留为最终架构，但不等待现场旋转参数；当前开发主线是单帧真实槽区域、第二侧壁和槽口端点定位。审阅表达只完成证据语义修正，不继续扩展可视化。
- Q: Mac 140张回放后能否把0.12放宽到0.14？ → A: 绝对不能。33个运行局部诊断的记录全部仍为SOURCE_INCONSISTENT；part-019的唯一假设复现已知混合边。稳定和接近阈值不证明正确，应先查粗区间、anchor、逐seed吸附、生成拒绝阶段和merge cluster。
- Q: 服务器140张diagnostic/2 trace证明了什么？ → A: part-019的另一真槽壁在side candidate生成前就缺失，不是0.5° merge丢失。原286.125°‒309.125°大暗区只向区间内部搜索，会稳定复现真槽一侧与fixture阴影一侧。
- Q: 新搜索能否越过原raw candidate端点？ → A: 必须。每个候选anchor同时向原区间内侧和外侧搜索，start可向更小角度、end可向更大角度扩展；原区间只作证据，不得作不可越过边界。

## User Scenarios & Testing

### User Story 1 - 两拍候选物理互证 (Priority: P1)

算法工程师将同一零件的两次拍摄和旋转元数据组成一对。系统保留每帧完整候选，把第二帧候选按有符号旋转量变回第一帧零件坐标；随零件旋转且唯一对应的候选可成为真槽假设，相机坐标近似固定的夹具阴影不得冒充真槽。

**Why this priority**: 跨帧运动规律比固定角屏蔽或单帧灰度对称假设更接近现场物理过程，可直接阻断稳定的混合边误检。

**Independent Test**: 用合成候选覆盖正负旋转、0/360环绕、真槽位于31°/328°、固定阴影不动和一帧被遮挡，检查唯一匹配与失败原因。

**Acceptance Scenarios**:

1. **Given** 两帧属于同一零件且旋转参数已确认，**When** 唯一候选随零件旋转且至少一帧无遮挡，**Then** 输出唯一真槽匹配、第二拍当前角和图像引导量。
2. **Given** 固定阴影在两帧相机角度近似不动，**When** 转到零件坐标，**Then** 它不满足真槽旋转一致性，不能被输出为真槽。
3. **Given** 真槽恰好位于31°或328°附近，**When** 它按已知旋转跨帧移动，**Then** 不得因固定角软先验而被屏蔽。
4. **Given** 多组候选形成同分或近同分匹配，**When** 唯一性差距不足，**Then** fail-closed并输出全部假设。

---

### User Story 2 - 未确认参数下安全联调 (Priority: P1)

现场可先生成成对清单并运行逐帧检测，即使旋转角、方向或误差仍为UNCONFIRMED，也能查看候选和缺失字段；系统不得把估计值包装成权威姿态。

**Why this priority**: 框架需要提前开发，但未知现场数值不能被程序默认值悄悄替代。

**Independent Test**: 使用参数为空或标为UNCONFIRMED的合法清单运行，确认输出DIAGNOSTIC_ONLY、valid=false、引导和PLC字段为空。

**Acceptance Scenarios**:

1. **Given** 双拍参数状态为UNCONFIRMED，**When** 两帧候选均可提取，**Then** 保留逐帧完整诊断但不输出权威配对角或引导量。
2. **Given** 只有暂定数值且状态仍为UNCONFIRMED，**When** 形成匹配假设，**Then** 假设明确标记非权威且valid=false。
3. **Given** 缺帧、SHA不符、pairId错配或旋转元数据非法，**When** 校验，**Then** 在使用图像结果前拒绝该对。

---

### User Story 3 - 遮挡时选择可信测量并闭环引导 (Priority: P2)

当两帧参数已确认且跨帧匹配唯一，只要至少一帧真槽无遮挡且几何可信，系统可用该帧测量建立零件相对槽方位，并换算到第二次拍摄后的当前图像姿态，输出朝左下85°±5°的最短图像旋转量。

**Why this priority**: 现场双拍的价值是保证至少一次无遮挡，同时设备最终姿态处于第二拍之后，不能误用第一拍旧角度。

**Independent Test**: 分别让第一帧或第二帧无遮挡，验证输出均以第二拍后的姿态为current angle；两帧均不可信时失败。

**Acceptance Scenarios**:

1. **Given** 第一帧无遮挡、第二帧被遮挡，**When** 跨帧匹配唯一，**Then** 从第一帧测量和已知旋转推导第二拍后的当前角。
2. **Given** 第二帧无遮挡，**When** 配对成立，**Then** 优先使用第二帧直接测量并报告来源。
3. **Given** 两帧均歧义或变换残差超限，**When** 评估，**Then** 不输出0度、不复用旧角度并明确失败。

---

### User Story 4 - 人工复核算法选边 (Priority: P2)

质量人员针对part-019的374/369查看原图与简化叠加并排联系表，并在预填LabelMe中确认或修正真槽、两处夹具阴影和算法左右槽壁是否同源；无需从空白图重画外圆。简化图不把算法候选包装成真值或valid结论。

**Why this priority**: 当前缺少结构化真值，肉眼指出的混合边必须转成可审计标签后才能裁决单帧门和双拍候选。

**Independent Test**: 对带单帧结果的临时图生成Git外材料，验证标签、颜色、图像SHA和AUTO_/human边界，且不把算法输出声明为真值。

**Acceptance Scenarios**:

1. **Given** 原图及019/020结果，**When** 生成审阅包，**Then** 每图包含原始分辨率的raw和simplified图、RAW/SIMPLIFIED联系表及LabelMe可打开的精简预填JSON。
2. **Given** 自动候选，**When** 写入LabelMe，**Then** 只保留最终左右槽壁、两槽口端点和fixture A/B候选，标签以AUTO_开头且human_verified=false，不写入外圆、定位框、raw暗区射线或人工真值。
3. **Given** 已有132112_4人工真值，**When** 做评估，**Then** 只作为Git外参考，不能进入生产运行时或成为待复核图的伪造标签。
4. **Given** 020提供raw start/center/end但没有二维像素边界，**When** 画简化图，**Then** 画开放角度括号和三刻线；只有角区间也缺失时才降级为候选方向，不画伪造的实心区域或红色真值框。

---

### User Story 5 - 暗区区间证据不冒充fixture真值 (Priority: P1)

人工复核者查看020观测到的圆周暗区区间。工具优先使用完整配对证据明确选中的candidateId；每个有start/center/end的raw candidate只画圆周角度括号和三条刻线，并同时显示候选编号、角度、match status及证据限制。PAIR_INCOMPLETE、NOT_MATCHED或缺失选择均不得显示为已确认fixture。

**Independent Test**: 构造完整配对、NOT_MATCHED、PAIR_INCOMPLETE和无区间payload，验证选择来源、形状类型、flags和画面声明。

**Acceptance Scenarios**:

1. **Given** pairEvidence.selectedCandidateIds存在且可追溯到raw candidate，**When** 生成审阅包，**Then** 只展示这些candidateId并保留其start/center/end和匹配检查。
2. **Given** 只有NOT_MATCHED或PAIR_INCOMPLETE，**When** 生成审阅包，**Then** 可展示观测暗区区间，但fixture_identity_confirmed=false且不得使用实心区域语义。
3. **Given** candidate有完整角度区间，**When** 写LabelMe，**Then** 使用AUTO_角度interval linestrip并记录boundary_semantics=angular_profile_interval、candidate_id、match_status、failed_checks。
4. **Given** start/end缺失但center可用，**When** 渲染，**Then** 才降级为方向箭头并明确Pixel boundary unknown。

---

### User Story 6 - 双向局部开口侧壁实验诊断 (Priority: P1)

算法工程师在020同源性拒绝后启用独立实验开关。系统把粗暗区两端仅视为待验证的anchor证据，对每个anchor向原区间内侧和外侧都枚举独立壁候选。候选不得被原start/end截断，但必须受可配置的物理槽宽与最大扩展约束。系统使用无序墙对判定同一局部方形开口，零解、多解或跨到fixture的组合继续安全失败。

**Independent Test**: 使用受控方形槽、邻近fixture、双解、缺边及31°/328°附近真槽合成证据验证枚举和fail-closed。

**Acceptance Scenarios**:

1. **Given** 真实另一壁位于原start的外侧，**When** 双向诊断，**Then** 向更小角度扩展的搜索域生成该壁候选，且不与区间内fixture边组成可通过墙对。
2. **Given** 真实另一壁位于原end的外侧，**When** 双向诊断，**Then** 向更大角度扩展的搜索域跨0°/360°安全生成该壁候选。
3. **Given** 同一方形开口只有一个无序墙对通过全部硬门，**When** 实验诊断，**Then** 输出唯一canonical pair及全部原始假设/failedChecks，但不提升为权威姿态。
4. **Given** 原错误大暗区内有fixture强边，**When** 外侧真壁和内侧fixture都被枚举，**Then** 跨越另一暗区或不符合同一方形开口的组合必须拒绝。
5. **Given** 零个或多个墙对通过，**When** 汇总，**Then** 状态分别为NOT_FOUND或AMBIGUOUS，valid=false且无权威角或PLC命令。
6. **Given** 真槽位于31°或328°附近，**When** 双向局部搜索，**Then** 不得因角度本身被屏蔽。

### Edge Cases

- 第二帧旋转跨越0°/360°，或方向为逆时针。
- 实际旋转偏差处于容差边界；恰好180°时多候选对称导致唯一性不足。
- 旋转量太小，无法区分相机固定阴影和随件真槽。
- 一帧无原始暗区、圆定位失败或只有拒绝候选；另一帧虽然有槽但无跨帧证据。
- 两帧来自不同sampleId、重复captureIndex、SHA重复或同一路径被配到多个pairId。
- 真槽与固定阴影在一帧重叠，但另一帧无遮挡；两帧都重叠时必须失败。
- 单帧输出契约版本不同或缺少完整候选；不得只读取旧的最终selected candidate冒充候选全集。
- 人工审阅包缺原图或结果SHA不匹配；不得生成看似可用的预标注。
- 原start/end本身就是混合真壁与fixture边；两者均不得因“已精修”而先验成为真壁。
- outward搜索跨0°/360°，或同时在两个方向找到几何可行强边。
- 候选位于物理槽宽上限外，或墙对之间穿过与当前开口不连通的第二暗区。

## Requirements

### Functional Requirements

- **FR-001**: 系统 MUST 提供版本化paired capture manifest，包含sampleId、pairId、恰好两个captureIndex、相对路径、图像SHA-256、nominalRotationDeg、rotationDirection、rotationToleranceDeg及parameterStatus。
- **FR-002**: parameterStatus MUST 支持CONFIRMED与UNCONFIRMED；UNCONFIRMED时旋转数值可为空或暂填，但不得产生权威引导。
- **FR-003**: 同一pair MUST 属于同一sampleId；captureIndex MUST 恰好为1和2；图像SHA、路径和pairId MUST 唯一且可审计。
- **FR-004**: 系统 MUST 复用现有单帧圆定位、原始暗区、槽识别、亚像素精修和同源性诊断，不得复制一套圆拟合算法。
- **FR-005**: 每帧输出 MUST 保留raw dark candidates、groove assessments、拒绝原因、精修/同源性证据，不能只保留最终选择。
- **FR-006**: 统一角度 MUST 使用图像x向右、y向下、profile从+x起顺时针；机械旋转正为顺时针。
- **FR-007**: 对已确认旋转，第二帧候选映射到第一帧零件坐标 MUST 使用 `wrap360(theta2 - signedRotationDeg)`，其中顺时针为正、逆时针为负。
- **FR-008**: 匹配 MUST 枚举跨帧一对一候选，输出角度残差、形状/剖面差、质量、最佳/次佳差距及所有拒绝原因。
- **FR-009**: 固定角31°/328°只可作为诊断软先验，MUST NOT 成为ignore mask或直接否决候选。
- **FR-010**: 只有跨帧匹配唯一、残差合格且至少一帧为无遮挡可信测量时，paired detection才可valid。
- **FR-011**: 缺帧、参数未确认、多解、候选过多、变换残差超限、两帧均不可信或配对身份不一致 MUST fail-closed。
- **FR-012**: 未确认参数但暂填数值时 MAY 输出非权威假设；状态 MUST 为DIAGNOSTIC_ONLY，valid=false且guidance/plc字段为空。
- **FR-013**: 第二拍后的currentAngleDeg MUST 与partRelativeGrooveAngleDeg分字段；前者从负Y轴顺时针有符号，后者标明零件坐标基准。
- **FR-014**: targetAngleDeg固定85、toleranceDeg固定5；检测有效但需调整不是检测失败，最短修正按wrapTo180计算，进入80°至90°死区输出0。
- **FR-015**: imageFrameCorrectionDeg与PLC/mechanical命令 MUST 分离；本功能不得写PLC，PLC映射未授权时必须为空。
- **FR-016**: 配置 MUST 版本化、严格拒绝未知字段，并含enabled=false默认值、候选上限、残差门、唯一性差距及形状门。
- **FR-017**: manifest、配置和输出 MUST 有JSON Schema与契约测试；非法输入在读取图像内容前拒绝。
- **FR-018**: 合成测试 MUST 覆盖正负旋转、环绕、31°/328°、单帧无遮挡、双帧歧义、错配和旋转误差。
- **FR-019**: part-006 MUST 继续封存，不得读取、重跑或用于参数选择。
- **FR-020**: 实验功能 MUST 默认关闭；默认单帧行为和legacy/paired/multi-role/single_real_groove契约 MUST 不变。
- **FR-021**: 审阅工具 MUST 在Git外为part-019 374/369生成原始分辨率raw、simplified、RAW/SIMPLIFIED两栏联系表、精简预填LabelMe JSON和review索引。
- **FR-022**: simplified和预填shape MUST 只保留AUTO_detected_groove_wall_left/right、AUTO_detected_mouth_endpoint_left/right、AUTO_observed_dark_angular_interval_*及明确标记非权威的AUTO_experimental_bidirectional_wall_candidate_*；MUST NOT 包含外圆、圆定位矩形框、非cluster代表的raw候选射线或自动人工真值框。
- **FR-023**: 审阅工具 MUST 核对原图SHA与两版结果SHA；不匹配时拒绝生成，媒体和绝对现场路径不得进入Git。
- **FR-024**: Pic_2026_08_13_132354_292.bmp MUST 暂时跳过；当前优先part-019的374与369。
- **FR-025**: 132112_4的人工圆弧和真槽开放边界 MAY 用作评估参考，MUST NOT 作为生产运行时输入或复制成其他图片真值。
- **FR-026**: simplified图 MUST 用稳定颜色和粗线显示019最终wall-left（绿）、wall-right（亮粉）及两个明显槽口端点；020暗区只能以橙色开放角度区间或无区间时的方向证据显示。
- **FR-027**: 每张simplified图 MUST 显示简短图例和“人工真实凹槽待确认”提示，并在标题列出019 valid状态和020 error code；图例 MUST 声明020所画候选不等于valid。
- **FR-028**: LabelMe预填 MUST 对所有shape使用AUTO_前缀并设置human_verified=false；人工标签保持空白，工具 MUST 拒绝覆盖已有非AUTO_或human_verified内容。
- **FR-029**: fixture审阅选择 MUST 优先使用`fixtureShadowEvidence.pairEvidence.selectedCandidateIds`；不得从NOT_MATCHED候选中按最近距离补出fixture A/B身份。
- **FR-030**: 有start/center/end的raw暗区 MUST 画圆周角度括号与三刻线并标candidateId、数值和match status；不得用实心扇区、polygon或“已定位区域”表达一维角度剖面。
- **FR-031**: 审阅图 MUST 逐项明确显示`Observed dark angular interval`、`Fixture identity unconfirmed`和`Pixel boundary unknown`；无start/end时才可降级为仅方向证据。
- **FR-032**: fixture AUTO_LabelMe shape MUST 为角度interval linestrip（无区间时为line），并包含fixture_identity_confirmed=false、boundary_semantics=angular_profile_interval、match_status、candidate_id、failed_checks；NOT_MATCHED/PAIR_INCOMPLETE不得标为confirmed或region。
- **FR-033**: 374/369 MUST 作为“019混合真槽壁+右上阴影壁”的语义负例；不得硬编码文件名、坐标或候选角修复，也不得把口头确认伪造成像素真值。
- **FR-034**: 系统 MUST 提供版本化`local_second_wall_diagnostic`实验配置，缺省或enabled=false时不执行、不改变020门限、状态、姿态或性能路径。
- **FR-035**: 局部诊断 MUST 把当前start/end仅视为待验证anchor；对每个anchor同时向coarse raw candidate内侧与外侧枚举墙候选，原start/end MUST NOT 作为不可越过的搜索边界。
- **FR-036**: 每个墙对假设 MUST 检查物理槽宽、两壁近似直且平行、径向深度/覆盖及差异、相邻外圆槽口端点、局部暗开口连续支持、槽肩/角点结构、边缘对比/梯度及归一化剖面同源性；跨越另一暗区或fixture证据的组合 MUST 拒绝。
- **FR-037**: 只有恰好一个假设通过且唯一性门成立时 MAY 输出`experimentalCandidate`；该候选 MUST 标记authoritative=false、posePromotionAllowed=false，原`GROOVE_SOURCE_INCONSISTENT`、valid=false、机械/PLC空值保持不变。
- **FR-038**: 零个通过返回LOCAL_SECOND_WALL_NOT_FOUND，多个通过返回MULTIPLE_LOCAL_OPENINGS；不得回填0度、旧角或权威姿态。
- **FR-039**: 局部搜索 MUST 与相机固定角无关；合成测试 MUST 覆盖31°和328°附近的同一方形槽可被搜索，而非被屏蔽。
- **FR-040**: 局部诊断 MUST 分字段区分CANDIDATE_MISSING、LOCAL_SECOND_WALL_NOT_FOUND、MULTIPLE_LOCAL_OPENINGS和SOURCE_INCONSISTENT，并输出failureStage；不得把不同阶段统一包装成识别失败。
- **FR-041**: 候选评估 MUST 标明分层layer和hardGate；局部区间/槽宽、直壁平行性、径向覆盖、同一外圆端点、暗开口连续性和侧壁来源矛盾均为硬拒绝，score只能排序证据，不能覆盖硬门。
- **FR-042**: 合成验证 MUST 量化任意旋转、0/360环绕、31°/328°、曝光/模糊、fixture对比与宽度不对称、部分重叠场景的两端点误差、槽中点角误差和fail-closed；单张132112_4只作development参考，不产生准确率声明。
- **FR-043**: 每个side search seed MUST 输出seed角、搜索窗口、极性、检测点数、拟合状态、拒绝阶段、failedChecks、拟合交点角、seed到拟合角差、直线参数及有限线段端点；不得只保留最终代表边。
- **FR-044**: side candidate merge MUST 输出每个cluster的极性、代表candidate、全部member/suppressed candidateId、seed角、拟合角、角扩展、merge阈值和选择规则；未拟合seed必须显式标记未进入cluster。
- **FR-045**: anchor MUST 输出来源侧、原始端点角、原始直线/点数/对比/梯度/径向剖面和所需相反极性；粗local interval MUST 明确标记来源为coarse raw dark candidate，以便判断搜索域是否跨真槽与fixture。
- **FR-046**: pre-merge hypotheses与最终hypothesis merge cluster MUST 分开输出；诊断摘要 MUST 按极性统计seed、拟合成功、失败阶段、cluster数量/大小并区分NO_EDGE_SIGNAL、SINGLE_EDGE_ATTRACTOR和MULTIPLE_EDGE_CLUSTERS。
- **FR-047**: 双向搜索的内侧扩展、外侧扩展、seed间距、每个域最大seed数和总候选上限 MUST 版本化且严格校验；最大扩展 MUST 受可配置物理槽宽范围约束，不得由part-019角度或坐标推导成运行时常量。
- **FR-048**: 墙候选 MUST 由多角度seed的径向梯度、直线共识与外圆交点独立生成；start/end只参与搜索域定位与证据比较，MUST NOT 被预先当作已确认两壁。
- **FR-049**: 墙对 MUST 使用与anchor顺序无关的canonical pair ID；A-anchor+B-candidate与B-anchor+A-candidate MUST 为同一对，不得作为两个假设后再依赖顺序merge。
- **FR-050**: 物理墙cluster merge MUST 只合并角度/线段证据真正相近的同一墙；不同墙 MUST 保留不同candidateId/clusterId，任何墙对去重不得删除物理候选。
- **FR-051**: 诊断输出 MUST 对每个anchor列出inward/outward搜索域、wrap360起止、seed角、拟合墙角、拒绝阶段、物理墙cluster、canonical pair ID及分层failedChecks。
- **FR-052**: 已知fixture证据只可作跨暗区/夹具来源的可观测证据，31°/328° MUST NOT 作屏蔽角；真槽在该位置时仍必须可枚举。
- **FR-053**: 140张回放 MUST 分别报告part-019是否形成新的外侧wall cluster、旧混合对是否仍拒绝、part-008的fail-closed结果及其他上游失败分布；无像素真值时不得称准确率或自动修复。
- **FR-054**: 374/369简化图 MUST 展示双向搜索得到的最终墙候选、搜索方向与不权威声明；用户未确认像素壁前，不得写入人工真值或提升pose。
- **FR-055**: 新路径 MUST 保持诊断默认关闭、`authoritative=false`、`posePromotionAllowed=false`、顶层原失败与PLC阻断；020的0.12门、默认配置及legacy/旧paired路径 MUST 不变。

### Key Entities

- **PairedCaptureManifest**: 数据集根相对的双拍身份、图像哈希和旋转参数状态。
- **CaptureFrame**: 一次拍摄及其captureIndex、图像身份、单帧结果和完整候选证据。
- **RotationContract**: 有符号旋转的名义值、方向、容差、状态和约定版本。
- **CandidateEvidence**: 单帧暗区/槽候选的角度、形状、质量、接受状态和可审计剖面。
- **CrossFrameHypothesis**: 两帧候选一对一对应、归一化角、残差、形状差和唯一性分数。
- **PairedPoseResult**: 配对状态、零件相对槽角、第二拍当前角、图像修正量和PLC阻断。
- **ReviewBundle**: 原图身份、两版算法叠加、AUTO_预标注和人工复核问题。
- **ObservedAngularInterval**: raw暗区的一维start/center/end、candidateId、match status与失败检查；不是fixture身份或二维像素边界。
- **LocalSecondWallHypothesis**: anchor侧、备选侧、局部开口证据、几何/剖面门、得分及failedChecks；只用于实验诊断。
- **BidirectionalSearchDomain**: anchor身份、inward/outward方向、wrap360区间、seed上限和物理扩展约束。
- **PhysicalWallCandidate**: 独立seed拟合出的墙角、有限线段、径向证据、外圆交点、cluster归属与拒绝阶段。
- **CanonicalWallPair**: 按稳定wall cluster ID排序的无序墙对、同一开口几何/灰度/连通性证据又failedChecks。

## Success Criteria

### Measurable Outcomes

- **SC-001**: 所有合法双拍清单100%可追溯到两个不同SHA；身份、参数或结构错误100%在图像检测前拒绝。
- **SC-002**: 合成真槽跨帧匹配在正负旋转和0°/360°环绕下残差计算正确到1e-9°，固定相机阴影不被唯一匹配为真槽。
- **SC-003**: 真槽位于31°或328°附近的测试100%证明不存在固定角硬屏蔽。
- **SC-004**: 0、多个匹配、两帧均遮挡、参数未确认和错配场景100%输出valid=false且无机械/PLC指令。
- **SC-005**: 至少一帧无遮挡且唯一匹配时，第二拍当前角和85°最短修正的数值测试覆盖顺/逆时针及80°/90°边界。
- **SC-006**: 默认配置下新增配对代码不执行，现有全量测试无回退。
- **SC-007**: part-019 374/369每图100%生成raw、simplified和精简AUTO_LabelMe；两行RAW/SIMPLIFIED联系表可直接对照，自动检查证明不含外圆/定位框/raw射线/伪真值框，且标签不冒充人工真值。
- **SC-008**: 功能分支通过全量单元测试、Schema、CLI、diff、JSON和媒体/绝对路径污染检查。
- **SC-009**: 未获得真实双拍BMP和确认旋转参数前，不宣称生产准确率、7组修复或可合入main。
- **SC-010**: NOT_MATCHED与PAIR_INCOMPLETE测试100%证明不产生fixture confirmed、实心区域或nearest候选身份补全；有区间的AUTO_shape 100%携带FR-032 flags。
- **SC-011**: 局部第二壁合成测试100%覆盖唯一方形槽成功、fixture跨源拒绝、多解、缺边和31°/328°；所有假设均可审计failedChecks。
- **SC-012**: 实验关闭时全量测试输出与020行为不变；实验开启且唯一诊断候选形成时，顶层仍为GROOVE_SOURCE_INCONSISTENT、valid=false且无权威姿态/PLC命令。
- **SC-013**: 受控曝光/模糊和任意旋转方形槽中，两端点误差各小于0.15°、中点角误差小于0.10°；fixture不对称/部分重叠不得形成跨源权威配对，零解/多解保持显式失败。
- **SC-014**: 合成trace测试100%证明每个seed可追溯到拒绝阶段或一个merge cluster、cluster成员无丢失、pre/post-merge假设可对账；Mac可从JSONL导出374/369脱敏trace而不读取或复制原图。
- **SC-015**: 合成测试100%覆盖另一壁位于start外侧、end外侧、0°/360°环绕、fixture位于内侧、双向多解与零解；原错误大区间混合对不得成为通过假设。
- **SC-016**: 每个拟合墙要么归属恰好一个physical wall cluster，要么保留明确拒绝阶段；每个无序墙对只出现一个canonical ID，端点顺序反转不改变ID或数量。
- **SC-017**: 140张回放100%产出可解析diagnostic/3 trace；part-019的外侧cluster数、旧混合对拒绝数、part-008安全状态及全部上游错误可分组汇总，但顶层姿态仍不因实验诊断提升。
- **SC-018**: 双向搜索的实际seed数和候选数不超过配置上限；默认关闭时不执行新路径，全量回归和原历史耗时门通过。

## Assumptions

- 双拍旋转方案已由现场确定为正式方向，但nominalRotationDeg、rotationDirection、rotationToleranceDeg和采集时序字段尚未确认。
- 两次拍摄间相机和夹具不动；固定阴影在相机坐标近似固定，真槽随零件旋转。该物理假设仍需真实配对数据验证。
- 当前开发只建立离线实验框架；不改PLC、上位机或默认单帧算法。
- 现有020单帧输出是每帧候选底座；part-019 374/369人工复核用于候选真实性，不是双拍精度真值。

## Out of Scope and Blocked

- **OUT-001**: 不实现PLC写入、机械执行、相机触发或设备时序控制。
- **OUT-002**: 不用固定角直接删除候选，不训练模型，不用sealed part-006调参。
- **OUT-003**: 不把019/020历史算法输出当人工真值。
- **BLOCKED-B01**: 现场需确认两拍旋转角、方向、重复误差/容差以及实际执行后零件是否停留在第二拍姿态。
- **BLOCKED-B02**: 真实配对BMP及其sampleId/pairId/captureIndex尚未提供，当前只能做合成和契约验证。
- **BLOCKED-B03**: PLC方向、缩放、地址和字节序仍未授权，paired image guidance不得升级为PLC命令。
- **BLOCKED-B04**: part-019 374/369尚需AUTO_预标注辅助下的人工确认；part-015 292明确跳过。
- **BLOCKED-B05**: 374/369现只有区域/混合来源语义确认，尚无像素级真实第二壁、槽口端点和两处fixture边界标签；局部实验结果不得作为准确率证据。
