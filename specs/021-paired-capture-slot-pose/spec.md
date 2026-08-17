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
- Q: 服务器140张diagnostic/2 trace证明了什么？ → A: part-019在side candidate生成阶段没有产生额外的可见墙cluster，不是0.5° merge丢失；它证明旧搜索域会稳定复现真槽一侧与fixture阴影一侧，但不能证明相对真槽壁在该帧一定可见。
- Q: 新搜索能否越过原raw candidate端点？ → A: 必须。每个候选anchor同时向原区间内侧和外侧搜索，start可向更小角度、end可向更大角度扩展；原区间只作证据，不得作不可越过边界。

### Session 2026-08-17

- Q: `HUMAN_true_groove_wall_missing`能否按标签字面作为“缺失的另一侧壁”真值？ → A: 不能。人工两点线`[[3266.0,258.5],[3226.0,331.0]]`与已有`AUTO_detected_groove_wall_left`/285.953°墙cluster近乎重合，语义应更正为`human-confirmed-visible-real-groove-wall`；原LabelMe文件和其SHA必须原样保留。
- Q: 这条人工线证明了什么？ → A: 它确认算法已找到的一条可见边确属真实凹槽；它没有提供另一侧壁、完整槽口、槽中点或角度真值。309.48°边仍是fixture shadow edge，不得与已确认真槽壁配对。
- Q: 单帧是否应继续“恢复”不可见的另一侧壁？ → A: 不应。另一侧壁的可观测性尚未确认且可能被遮挡；局部Cartesian搜索只能枚举图像中实际存在的可审计证据，不能推断或合成不可见像素。当前运行时继续fail-closed；如未来增加`PARTIALLY_OBSERVED`，只能是版本化诊断状态，不能使姿态valid或产生引导/PLC命令。
- Q: 这是否改变双拍方向？ → A: 不改变。双拍的核心价值正是保证至少一拍无遮挡；只有无遮挡帧提供完整同源两壁和槽口几何时，才可形成权威单帧测量并参与跨帧互证。

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

算法工程师在020同源性拒绝后启用独立实验开关。系统把粗暗区两端仅视为待验证的anchor证据，对每个anchor向原区间内侧和外侧都枚举图像中可观测的独立壁候选。候选不得被原start/end截断，但必须受可配置的物理槽宽与最大扩展约束。系统使用无序墙对判定同一局部方形开口，零解、多解、跨到fixture或只有一条可见真壁的情况继续安全失败；本诊断不得承担“补造被遮挡侧壁”的职责。

**Independent Test**: 使用受控方形槽、邻近fixture、双解、缺边及31°/328°附近真槽合成证据验证枚举和fail-closed。

**Acceptance Scenarios**:

1. **Given** 真实另一壁位于原start的外侧，**When** 双向诊断，**Then** 向更小角度扩展的搜索域生成该壁候选，且不与区间内fixture边组成可通过墙对。
2. **Given** 真实另一壁位于原end的外侧，**When** 双向诊断，**Then** 向更大角度扩展的搜索域跨0°/360°安全生成该壁候选。
3. **Given** 同一方形开口只有一个无序墙对通过全部硬门，**When** 实验诊断，**Then** 输出唯一canonical pair及全部原始假设/failedChecks，但不提升为权威姿态。
4. **Given** 原错误大暗区内有fixture强边，**When** 外侧真壁和内侧fixture都被枚举，**Then** 跨越另一暗区或不符合同一方形开口的组合必须拒绝。
5. **Given** 零个或多个墙对通过，**When** 汇总，**Then** 状态分别为NOT_FOUND或AMBIGUOUS，valid=false且无权威角或PLC命令。
6. **Given** 真槽位于31°或328°附近，**When** 双向局部搜索，**Then** 不得因角度本身被屏蔽。
7. **Given** 人工只确认一条可见真槽壁且相对侧没有可靠像素证据，**When** 局部诊断运行，**Then** 保留该可见壁及观测性说明，但不得生成另一侧壁真值、完整槽中点、有效姿态或PLC命令。

---

### User Story 7 - 部分观测诊断与完整槽人工复核队列 (Priority: P1)

算法工程师需要把“有墙状像素证据但无法形成完整同源槽口”与“完全没有候选”分开，同时从冻结140张中选择极少量最可能已具备两壁证据的帧供人工确认。人工确认不进入生产运行时，已知part-019混合边只作负例。

**Why this priority**: 初版必须能安全说明单侧可见/遮挡，而完整槽姿态链又需要新的两壁人工真值；两者不能通过放宽门限或把算法输出当真值解决。

**Independent Test**: 用单壁、真壁+fixture混合边、完整同源双壁和无墙候选合成场景验证状态；用多个物理零件的manifest+JSONL验证队列选择稳定、排除已知partial组且不泄漏角度真值。

**Acceptance Scenarios**:

1. **Given** 至少一个墙状cluster可观测但没有完整同源唯一墙对，**When** 局部诊断汇总，**Then** 输出`PARTIALLY_OBSERVED`、`authoritative=false`、`posePromotionAllowed=false`，并明确完整槽未观测。
2. **Given** 374式真壁+fixture混合边，**When** 配对失败，**Then** 不产生`experimentalCandidate`、槽中点或角度；顶层仍为`GROOVE_SOURCE_INCONSISTENT`和`valid=false`。
3. **Given** 两侧真实槽壁完整可见且同源门通过，**When** 正常single_real_groove链运行，**Then** 输出唯一完整槽口、当前角和到85°±5°的图像有符号修正量，PLC仍为空。
4. **Given** 140张manifest与结果，**When** 生成最小复核队列，**Then** 先按物理sample汇总是否到达双壁证据阶段，再在候选sample内用SHA稳定选择，不依据角度误差或最终算法表现挑帧。
5. **Given** part-019已知partial/mixed语义，**When** 选择完整槽候选，**Then** 它作为负例记录但不进入“可能完整槽”正向队列；所有队列项保持humanVerified=false。

---

### User Story 8 - 完整槽语义确认后的局部fixture污染标注 (Priority: P1)

人工复核者已经确认part-008的145与147中，两条检测墙属于同一个真实方形槽、两侧完整无遮挡且两个端点位于真实外圆槽肩；同时确认有部分标记线落在fixture shadow上，但不是整条线。工程师需要保留这组混合语义，并把下一步缩小为定位受污染的墙及其局部子段，不能把整条AUTO线升级成像素真值。

**Why this priority**: 该结论首次确认了真实完整槽身份，但也证明AUTO几何并非干净像素真值。先定位污染子段才能判断污染发生在显示延长线还是实际拟合支持点；在此之前调门限会混淆真实槽证据与fixture证据。

**Independent Test**: 使用临时review-index、AUTO LabelMe和两个明确imageId，验证语义响应按SHA关联、AUTO shapes逐点不变、输出只创建待人工补画的污染子段请求；错误SHA、未知imageId、已有HUMAN shape或非PARTIAL语义均在写出前拒绝。

**Acceptance Scenarios**:

1. **Given** 145/147的四项人工回答为YES、YES、YES、YES且污染范围为PARTIAL，**When** 记录语义复核，**Then** 分别保留“真实槽身份确认”“槽肩端点语义确认”“整条AUTO线不是像素真值”“局部fixture污染待定位”四类状态。
2. **Given** 现有AUTO LabelMe，**When** 生成下一步标注请求，**Then** 原AUTO shapes和点坐标逐项保持不变，工具不得自动新增任何HUMAN坐标。
3. **Given** 人工开始局部污染标注，**When** 保存LabelMe，**Then** 只需用HUMAN_fixture_shadow_overlap_on_detected_wall_left和/或HUMAN_fixture_shadow_overlap_on_detected_wall_right的linestrip描出实际受污染子段，不重画完整槽。
4. **Given** 只有语义回答而没有污染子段像素坐标，**When** 评估准确率或修改门限，**Then** pixelTruthAvailable=false、cleanAccuracyEvaluationAllowed=false、thresholdTuningAllowed=false和runtimeInputAllowed=false。
5. **Given** 后续获得污染子段，**When** 开展诊断，**Then** 必须分别报告污染段与显示线、实际拟合支持点、槽口端点的重叠；不得仅凭肉眼回答推断哪一侧或哪一批支持点受污染。

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
- 人工shape的label名称与实际几何语义冲突；必须保留原件并通过派生审核副本更正语义，不能按名称自动纳入真值。
- 单帧只看得到一条真实槽壁；不得把最邻近强边或fixture阴影补成第二壁。
- 人工确认真实槽身份但同时确认局部fixture污染；不得把“身份正确”改写为“整条像素线干净”。

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
- **FR-038**: 零个完整墙对通过时，若没有墙状像素证据则返回LOCAL_SECOND_WALL_NOT_FOUND；若至少一个墙cluster存在但未建立完整同源唯一槽口，则返回PARTIALLY_OBSERVED并遵循FR-062—FR-065；多个完整通过解返回MULTIPLE_LOCAL_OPENINGS。任一分支均不得回填0度、旧角或权威姿态。
- **FR-039**: 局部搜索 MUST 与相机固定角无关；合成测试 MUST 覆盖31°和328°附近的同一方形槽可被搜索，而非被屏蔽。
- **FR-040**: 局部诊断 MUST 分字段区分CANDIDATE_MISSING、LOCAL_SECOND_WALL_NOT_FOUND、PARTIALLY_OBSERVED/PARTIAL_GROOVE_OBSERVATION、MULTIPLE_LOCAL_OPENINGS和SOURCE_INCONSISTENT，并输出failureStage；不得把不同阶段统一包装成识别失败。
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
- **FR-056**: Git外原始人工LabelMe及其SHA-256 MUST 原样保留；语义修正只能生成新的派生审核副本，MUST NOT 覆盖或静默改写原件。
- **FR-057**: 原label `HUMAN_true_groove_wall_missing` MUST 按审核语义解释为`human-confirmed-visible-real-groove-wall`，且 MUST 明确记录`opposite_wall_truth=false`；不得把其两点线用作另一侧壁训练、门限选择或端点精度真值。
- **FR-058**: part-019 374当前证据 MUST 区分：285.953°cluster为人工确认的可见真实槽壁，309.48°边为fixture shadow edge且禁止配对；该确认不得外推为完整槽、槽中点或姿态准确率。
- **FR-059**: 单帧只有一条可见真壁或另一壁可观测性不明时，当前运行时 MUST 保持fail-closed、`valid=false`、无权威角和无PLC命令；系统 MUST NOT 从不可见像素合成第二壁。未来若增加`PARTIALLY_OBSERVED`，必须升版并保持其为非权威诊断状态。
- **FR-060**: 局部Cartesian/双向侧壁搜索 MAY 发现原区间外实际可见的墙证据，但 MUST NOT 把“搜索不到”解释为真实壁坐标缺失或要求人工猜线；只有两侧均有可审计像素证据时才可评估完整开口。
- **FR-061**: 双拍配对在生产提升姿态前 MUST 至少有一帧完整、无遮挡、同源两壁可观测；若两帧都只有部分观测或完整帧不唯一，MUST fail-closed。
- **FR-062**: 局部墙诊断输出 MUST 升版并支持`PARTIALLY_OBSERVED`；该状态只表示存在墙状像素证据但未建立完整同源唯一槽口，不得声明任何候选是真槽真值。
- **FR-063**: `PARTIALLY_OBSERVED` MUST 保持`authoritative=false`、`posePromotionAllowed=false`、`experimentalCandidate=null`，且完整槽中点、当前角、修正角和PLC命令均不可用。
- **FR-064**: 部分观测输出 MUST 列出observed wall cluster ID、证据数量、`completeSameSourceOpeningObserved=false`、`humanConfirmationAppliedAtRuntime=false`和`oppositeWallObservability=UNCONFIRMED`，以区分运行时证据与Git外人工审核。
- **FR-065**: 局部诊断为`PARTIALLY_OBSERVED`时，外层slot-pose结果 MUST 继续使用现有`GROOVE_SOURCE_INCONSISTENT`、`DETECTION_FAILED`、`guidanceStatus=NOT_AVAILABLE`和`valid=false`；不得新增PLC路径或把partial当检测成功。
- **FR-066**: 完整同源两壁通过现有refinement与source-consistency门时，single_real_groove正常链 MUST 保持`DETECTED`、valid图像测量、85°±5°死区与最短有符号修正语义，不得被partial状态改动回退。
- **FR-067**: part-019混合边回归 MUST 保留`reuses_rejected_initial_pair`及source inconsistency硬拒绝；309.48°fixture边不得与285.953°已确认真壁形成完整槽口。
- **FR-068**: 系统 MUST 提供只读、路径安全的完整槽人工复核队列CLI，输入一个或多个冻结manifest与对应JSONL，按sample汇总上游阶段、双壁refinement/cluster证据及已知人工排除项。
- **FR-069**: 队列选择 MUST 先选具有双壁像素证据且未被人工标为partial/mixed的sample，再在sample内用`sha256(sampleId|sourceImageSha256)`稳定选择至多配置数量；MUST NOT 依据预测角、修正量、85°接近度或门限距离选帧。
- **FR-070**: 队列JSON、CSV和review manifest MUST 写到Git外，使用A2根相对路径与图像SHA，标记`accuracyEvaluated=false`、`algorithmOutputIsTruth=false`、`humanVerified=false`并列出最小复核问题；媒体和运行JSONL不得提交Git。

- **FR-071**: 系统 MUST 原样记录145/147四项语义回答：同一真实方形槽=YES、两侧完整无遮挡=YES、两端点位于真实外圆槽肩=YES、存在fixture shadow标记线=YES且范围为PARTIAL；不得将任一项弱化、合并或反向解释。
- **FR-072**: 语义确认 MUST 分离realGrooveIdentityConfirmed、endpointSemanticsConfirmed、fixtureShadowContaminationExtent和pixelTruthAvailable；前三者不得自动使AUTO墙坐标成为真值。
- **FR-073**: 系统 MUST 提供版本化、Git外的fixture污染复核记录，按imageId、sourceImageSha256和sourceReviewIndexSha256关联来源，重复或不匹配身份在写出前拒绝。
- **FR-074**: 污染标注请求 MUST 逐点保留现有AUTO墙和端点shape，不得自动新增HUMAN坐标、不得覆盖已有人工内容，并保持runtimeInputAllowed=false。
- **FR-075**: 最小人工标注 MUST 只要求以left/right专用HUMAN linestrip描出fixture shadow与对应检测墙重叠的局部子段；不得要求重画完整槽或把未标部分解释为干净像素真值。
- **FR-076**: 未取得污染子段坐标前，affectedWall、supportPointOverlap、endpointOverlap MUST 保持UNCONFIRMED；cleanAccuracyEvaluationAllowed和thresholdTuningAllowed MUST 为false。
- **FR-077**: 后续污染诊断 MUST 区分显示线延长、实际拟合支持点和槽口端点三类几何，并分别报告与人工污染子段的重叠，不得仅凭语义回答调整门限。
- **FR-078**: 语义复核、派生LabelMe和污染诊断 MUST 禁止作为生产运行时输入或PLC输入；145/147不得在污染定位完成前用于准确率声明或阈值选择。

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
- **HumanVisibleWallReview**: 原人工shape身份与SHA、派生语义标签、两点几何、`oppositeWallTruth=false`和观测性限制；只证明一条可见真实槽壁。
- **PartialWallObservation**: 运行时墙状cluster集合、未形成完整同源槽口的原因和非权威边界；不含人工真壁身份。
- **CompleteGrooveReviewQueue**: 按物理sample汇总、人工排除项、稳定选帧规则、相对路径/SHA和待回答问题；不含角度真值。
- **CompleteGrooveSemanticReview**: 以图像身份/SHA关联的四项人工语义回答、PARTIAL污染范围及所有禁止升权策略；不含像素坐标。
- **FixtureContaminationAnnotationRequest**: 从AUTO LabelMe派生的Git外请求，保留原shape并仅声明允许人工补画的left/right污染子段标签。

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
- **SC-019**: 语义派生审核副本100%保留原人工shape两点，记录原文件SHA且不覆盖原件；误命名label不会进入另一侧壁真值或运行时输入。
- **SC-020**: 一条人工确认真壁加一条fixture边的回归场景100%保持`valid=false`且不产生完整槽中点、姿态或PLC命令；0.12门限和默认配置不变。
- **SC-021**: 单墙cluster和仅source-inconsistent墙对测试100%输出`PARTIALLY_OBSERVED`及完整FR-064证据；0墙保持NOT_FOUND，多完整解保持AMBIGUOUS。
- **SC-022**: 374混合边结构回归100%无`experimentalCandidate`、无完整槽端点/中点和无图像引导；已拒绝初始对不能重新通过。
- **SC-023**: 完整双壁合成运行时100%保持既有`DETECTED`、当前角、85°目标、最短有符号修正和PLC阻断契约。
- **SC-024**: 140张候选盘点100%按sampleId对账且不含sealed part-006；最小正向复核队列不含已知partial part-019，队列顺序对输入manifest/JSONL顺序不敏感。
- **SC-025**: 新Schema、CLI和全量测试通过；默认关闭路径、0.12同源门、0.5°墙merge、main和PLC均不改变。

- **SC-026**: 145与147的语义记录100%保持YES/YES/YES/YES+PARTIAL，并同时保持autoLinesArePixelTruth=false、cleanAccuracyEvaluationAllowed=false和thresholdTuningAllowed=false。
- **SC-027**: 临时审阅包测试100%证明派生前后AUTO shapes及其点坐标完全相同，且工具输出0个自动HUMAN shape。
- **SC-028**: 未知imageId、SHA不一致、AUTO文件哈希不一致、已有HUMAN内容和非PARTIAL响应100%在写出污染请求前拒绝。
- **SC-029**: 污染请求中的每个条目只允许left/right两种HUMAN linestrip标签，affectedWall、supportPointOverlap和endpointOverlap在人工补画前均为UNCONFIRMED。
- **SC-030**: 新Schema、CLI、聚焦和全量测试通过；图像算法、140张结果、0.12同源门、0.5°墙merge、main和PLC均不改变。

## Assumptions

- 双拍旋转方案已由现场确定为正式方向，但nominalRotationDeg、rotationDirection、rotationToleranceDeg和采集时序字段尚未确认。
- 两次拍摄间相机和夹具不动；固定阴影在相机坐标近似固定，真槽随零件旋转。该物理假设仍需真实配对数据验证。
- 当前开发只建立离线实验框架；不改PLC、上位机或默认单帧算法。
- 现有020单帧输出是每帧候选底座；part-019 374的人工线只确认一条可见真实槽壁，不是另一壁、完整槽或双拍精度真值。

## Out of Scope and Blocked

- **OUT-001**: 不实现PLC写入、机械执行、相机触发或设备时序控制。
- **OUT-002**: 不用固定角直接删除候选，不训练模型，不用sealed part-006调参。
- **OUT-003**: 不把019/020历史算法输出当人工真值。
- **BLOCKED-B01**: 现场需确认两拍旋转角、方向、重复误差/容差以及实际执行后零件是否停留在第二拍姿态。
- **BLOCKED-B02**: 真实配对BMP及其sampleId/pairId/captureIndex尚未提供，当前只能做合成和契约验证。
- **BLOCKED-B03**: PLC方向、缩放、地址和字节序仍未授权，paired image guidance不得升级为PLC命令。
- **BLOCKED-B04**: part-019 374的一条可见真槽壁已获得人工语义确认；369仍未形成同等级像素确认，part-015 292明确跳过。
- **BLOCKED-B05**: 374的相对侧真实壁是否可见仍未确认，且尚无完整槽口端点、槽中点和两处fixture二维边界标签；不得要求人工猜不可见线，局部实验结果也不得作为准确率证据。
- **RESOLVED-R02**: part-008的145/147均已获得相同语义回答：两墙同属真实方形槽、两侧完整无遮挡、端点位于真实外圆槽肩，同时存在局部而非整条fixture shadow污染。
- **BLOCKED-B06**: 145/147尚未标出具体受污染的left/right墙及像素子段；无法判断污染是否进入拟合支持点或触及端点，完成该最小标注前不得调门限或声明干净像素精度。
- **RESOLVED-R01**: 服务器已在Git外复核原始人工LabelMe、安全派生副本和压缩包SHA-256；三者不得提交Git，派生副本仍禁止作为运行时或完整槽姿态真值。
