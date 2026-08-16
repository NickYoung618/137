# Feature Specification: A2 多组静态重复性与过渡盲测治理

**Feature Branch**: `009-a2-static-repeatability-governance`

**Created**: 2026-08-16

**Status**: Draft

**Input**: 用户要求按物理零件与固定工况建立多组静态重复性评价、统一A2路径、冻结可审计的过渡盲测组，并提供Mac可复现CLI；不得修改槽姿态核心算法或把已查看的700张宣称为严格未见测试。

## Clarifications

### Session 2026-08-16

- 用户确认A2编号每20张对应一个物理零件；normal 481–500属于同一零件，但481–498与499–500之间发生旋转，必须作为两个不同condition保留并从正式静态重复性统计排除。
- 用户确认静态重复性采用多组分别评价后总体汇总，且至少覆盖目标附近、需要顺时针调整、需要逆时针调整三类工况。
- 用户确认当前700张已被查看，不能宣称严格未见测试；过渡盲测必须按完整物理零件冻结、选择规则与哈希可审计且不得依据算法表现。

## User Scenarios & Testing

### User Story 1 - 建立可信的物理分组与资格表 (Priority: P1)

作为算法和质量负责人，我需要从统一A2根目录清单与人工确认的分组记录中建立可追溯Manifest，并明确每组是否具备静态重复性资格，从而避免把目录、文件数量或空字段误当成物理真值。

**Why this priority**: 所有重复性、盲测和泄漏检查都依赖正确的物理样品与工况身份。

**Independent Test**: 使用不含现场路径的合成清单验证统一根路径、空分组拒绝、完整组通过、短组排除、bad语义阻塞和物理样品跨split拒绝。

**Acceptance Scenarios**:

1. **Given** 一个仅含可靠路径、哈希、类别和采集序号的inventory draft，**When** sample/condition/repeat仍为空，**Then** 系统保留其draft身份且拒绝将其冒充显式grouping。
2. **Given** 一个经负责人确认的20帧同样品、同装夹、同角度、同工况连续组，**When** 生成资格表，**Then** 该组为静态评价候选并记录authority/provenance。
3. **Given** normal 481–500属于同一样品但在498/499之间旋转，**When** 分组，**Then** 481–498与499–500使用相同sampleId、不同conditionId，并分别因18帧和2帧被排除。
4. **Given** bad组缺少badReason或poseUsable权威确认，**When** 生成资格表，**Then** 该组保留但不进入权威静态汇总。

---

### User Story 2 - 输出多组静态重复性报告 (Priority: P1)

作为现场负责人，我需要看到每个合格静态组的角度、圆与槽几何、检测有效率和耗时，以及跨组汇总与三类引导工况覆盖，从而判断算法稳定性而不混淆检测失败、当前姿态和调整方向。

**Why this priority**: 单一参考图或单组极差不能代表工业现场的重复性。

**Independent Test**: 用跨±180°、检测失败、不同当前角度和不同几何波动的受控结果验证逐组及总体统计。

**Acceptance Scenarios**:

1. **Given** 多个合格静态组，**When** 生成报告，**Then** 每组输出角度环形极差、环形标准差、P95绝对残差、检测有效率、圆心/半径/槽口中点像素波动和单图耗时P50/P95/max。
2. **Given** 不同组位于不同真实角度，**When** 总体汇总，**Then** 系统汇总各组中心化后的残差与最差组指标，不对原始角度直接求跨组极差。
3. **Given** 当前角度不在85°±5°，**When** 检测和几何有效，**Then** 该帧仍计为检测有效，并单独记录需要顺时针或逆时针调整。
4. **Given** 一组包含检测失败，**When** 统计，**Then** 失败帧进入有效率分母且角度/几何字段保持缺失，不填0。

---

### User Story 3 - 冻结可审计的过渡盲测组 (Priority: P2)

作为项目负责人，我需要按与算法结果无关、可复算的规则选择并冻结一个完整物理零件作为过渡盲测，在开发期间隐藏逐图结果，并在发布候选完成后只运行一次。

**Why this priority**: 已查看700张不能提供严格无偏测试，但仍可通过预先承诺降低继续调参泄漏风险。

**Independent Test**: 对打乱输入顺序的合成样品清单执行选择，验证选中样品不变、全部condition随样品一起冻结、Manifest与锁文件SHA稳定、跨split泄漏被拒绝。

**Acceptance Scenarios**:

1. **Given** 多个完整且语义合格的物理样品，**When** 冻结过渡盲测，**Then** 仅使用清单身份和源图哈希的确定性规则选中一个完整sample，绝不读取算法结果。
2. **Given** 700张此前已被查看，**When** 输出锁文件，**Then** blindStatus明确为`NON_STRICT_TRANSITIONAL`并说明需新增零件才能建立正式未见测试。
3. **Given** 一个sample包含多个condition，**When** 冻结，**Then** 该sample的所有图像都进入同一purpose，不能拆分跨split。

---

### User Story 4 - Mac一键复现与安全判读 (Priority: P2)

作为Mac现场使用者，我需要从统一A2根目录和外置CSV生成受控Manifest、运行检测、生成重复性报告并阅读排除原因，同时保证媒体、绝对路径和人工真值不进入Git。

**Why this priority**: 工具只有在Mac现场可复现且判读不会误导时才可验收。

**Independent Test**: 在临时目录运行完整dry-run，验证输出位置、Schema、哈希、错误退出码和中文quickstart命令。

**Acceptance Scenarios**:

1. **Given** Mac本地A2数据根、inventory和人工确认CSV，**When** 运行CLI，**Then** 生成Manifest、资格表、冻结锁、批量结果输入约定和多组报告，且仓库内不记录Mac绝对路径。
2. **Given** 路径基准不匹配、源图哈希变化、分组不完整或样品跨split，**When** 运行CLI，**Then** 在检测前失败并给出明确错误。

### Edge Cases

- 路径以统一A2根为锚点，但normal图位于根下、bad图位于子目录；不得递归重复计数。
- 两类目录可能包含同名文件或同一物理零件；没有负责人证据时sampleId必须class-qualified或保持阻塞，不能仅凭目录合并。
- 20帧候选段存在时间戳回跳、丢帧、插帧或中途旋转时，必须拆分condition并保留原始顺序证据。
- 角度跨越±180°时，平均、标准差、极差和残差必须采用环形计算。
- 一个组虽然采集帧数达到20，但有效检测不足以计算某项统计时，该项为不可用且不得以0代替。
- 过渡盲测候选不足、选择后文件变化、锁文件已存在且内容不同、或请求第二次执行时，必须失败并保留既有锁。

## Requirements

### Functional Requirements

- **FR-001**: 系统MUST以单一、显式声明的数据根解析所有`relativePath`，且只处理inventory列出的图像，不得通过normal/bad双root递归产生重复或遗漏。
- **FR-002**: inventory draft与explicit grouping MUST是不同状态；sampleId、conditionId、repeatIndex任一为空时不得标记`groupingExplicit=true`。
- **FR-003**: 每条源图记录MUST保留安全相对路径、不可变SHA-256、datasetClass、采集序号/时间证据和分组authority/provenance。
- **FR-004**: 正式静态组MUST属于同一物理样品、同一次摆放/装夹、同一角度和采集条件，并连续包含至少20帧。
- **FR-005**: 重新摆放、旋转或工况改变MUST创建新conditionId；同一物理零件在不同condition中MUST保持相同sampleId。
- **FR-006**: 481–498和499–500 MUST保留为同sample、不同condition，并分别输出`FRAME_COUNT_LT_20`排除原因。
- **FR-007**: bad组只有在每条记录的badReason和poseUsable具有非算法来源的authority/provenance时，才可进入权威静态重复性汇总。
- **FR-008**: normal与bad是否共享物理样品不得由目录名推断；未知时MUST使用不会错误合并的class-qualified sample identity并报告假设。
- **FR-009**: 分组验证MUST拒绝路径/哈希不匹配、缺行、多余行、重复repeat、repeat不连续、一个sample跨split或同一source lineage跨split。
- **FR-010**: 每个合格静态组MUST报告角度环形极差、环形标准差、P95绝对环形残差、检测有效率和有效/失败数。
- **FR-011**: 每个合格静态组MUST报告圆心X/Y、半径和槽口中点X/Y的像素波动，以及elapsedMs的P50/P95/max；字段不可用时必须给出原因。
- **FR-012**: 跨组汇总MUST使用组内中心化环形残差，不得对不同当前角度组的原始角度直接求动态极差。
- **FR-013**: 报告MUST分别统计`DETECTED_IN_POSITION`、顺时针调整、逆时针调整和`DETECTION_FAILED`，当前位置偏离85°±5°不得视为检测失败。
- **FR-014**: 覆盖报告MUST明确目标附近、顺时针调整、逆时针调整三类合格静态工况是否各至少存在一组，缺失时保持BLOCKED而不伪造。
- **FR-015**: 失败帧MUST保留在检测有效率分母中，失败角度、几何和调整量MUST为null且不得填0。
- **FR-016**: 系统MUST以仅依赖sample identity、source hashes和固定公开规则的确定性选择冻结一个完整物理样品，禁止读取结果、角度、有效率或错误码选组。
- **FR-017**: 过渡盲测锁MUST包含选择算法版本、候选摘要、选中sample/conditions、完整图像哈希、Manifest SHA-256、创建时间、运行次数策略和`NON_STRICT_TRANSITIONAL`状态。
- **FR-018**: 过渡盲测sample的所有图像MUST属于同一purpose；开发及阈值选择期间不得输出其逐图检测结果，发布候选完成后最多执行一次。
- **FR-019**: 当前700张MUST明确标为已查看的锁定回归/非严格过渡证据，不能宣称独立accuracy test；正式测试仍需新增物理零件。
- **FR-020**: CLI与Schema MUST支持Mac统一A2根、外置inventory/grouping/semantics、资格表、冻结Manifest及多组报告的可复现工作流。
- **FR-021**: 本功能MUST不修改槽检测、圆拟合、槽壁精修、85°引导或PLC契约；发现核心缺陷时必须另行规格化。
- **FR-022**: 图片、结果媒体、绝对现场路径、人工真值和私有分组文件MUST留在Git外；仓库只保存模板、Schema、代码、测试与脱敏证据。
- **FR-023**: 所有输出MUST区分检测有效性、当前角、目标角、最短调整量、方向、到位状态和PLC不可用状态。

### Key Entities

- **Canonical Inventory**: 统一数据根下700张不可变源图的路径、类别、采集证据和哈希；可以处于draft状态。
- **Confirmed Grouping Record**: 经负责人确认的物理sample、condition、repeat与provenance，不携带算法表现。
- **Static Group Eligibility**: 每个sample/condition的帧数、语义覆盖、资格状态与排除原因。
- **Static Repeatability Group Result**: 单组角度、检测率、几何波动、耗时和引导工况统计。
- **Static Repeatability Summary**: 对合格组的中心化残差、最差组、总体有效率和三工况覆盖汇总。
- **Transitional Blind Lock**: 确定性选择规则、完整sample及图像哈希、非严格盲测声明与只运行一次策略。

## Success Criteria

### Measurable Outcomes

- **SC-001**: 受控测试中，空sample/condition/repeat的700行inventory不能生成显式grouping，错误在图像检测前给出。
- **SC-002**: 统一根dry-run对每条inventory路径恰好处理一次，normal/bad子目录布局不会重复计数。
- **SC-003**: 20帧合格组进入资格表；18帧和2帧组均以`FRAME_COUNT_LT_20`排除且原记录零删除。
- **SC-004**: bad语义未知组100%被排除在权威静态汇总之外，并保留明确阻塞原因。
- **SC-005**: 每个合格组均输出需求规定的角度、检测率、圆/槽几何和耗时字段；缺失值从不以0填充。
- **SC-006**: 跨±180°合成测试的环形极差、标准差和P95残差与解析真值一致，跨组汇总不受组中心角不同影响。
- **SC-007**: 三种引导工况分别计数，偏离目标但检测有效的帧100%保持检测有效。
- **SC-008**: 冻结选择对输入行顺序不敏感，不读取结果文件，并将同一样品全部图像置于同一purpose。
- **SC-009**: 冻结Manifest和锁文件的SHA-256可在Mac重复验证；已查看700张始终标记`NON_STRICT_TRANSITIONAL`。
- **SC-010**: 所有既有测试与新增聚焦测试通过，全部JSON Schema通过Draft 2020-12校验，真实数据dry-run不读取或修改原始BMP。
- **SC-011**: Git差异不包含图片、视频、压缩包、大文件、私有清单、人工真值或Mac/服务器现场绝对路径。

## Assumptions

- 用户对“每20张对应一个物理零件”的确认是当前分组权威来源；时间、像素差和算法几何仅作支持证据，不取代负责人确认。
- normal与bad跨目录是否为同一物理零件尚未确认，因此默认身份需要class-qualified并在报告中明确该假设。
- 当前700张已被算法开发者查看，任何从中冻结的组都只能是降低后续泄漏风险的过渡盲测，不能恢复成严格未见测试。
- 85°目标、顺时针为正、负Y下半轴基准及PLC安全边界沿用Spec 007，不在本功能中改变。
- 静态重复性本轮报告数值与覆盖状态，不新增未经质量负责人确认的PASS/FAIL阈值。

## Dependencies and Blocked Decisions

- **BLOCKED-B01**: 采集负责人仍需提供normal与bad是否共享物理零件的映射；确认前使用class-qualified identity。
- **BLOCKED-B02**: badReason、poseUsable及其authority/provenance未完成时，bad组不能进入权威静态重复性。
- **BLOCKED-B03**: 新采、未被开发过程查看且物理样品隔离的数据仍是严格validation/test的必要条件。
- **BLOCKED-B04**: 静态重复性PASS/FAIL门限需由质量负责人结合设备节拍和允许角误差另行确认。

## Out of Scope

- 修改槽姿态核心检测、圆拟合、槽识别、槽壁亚像素精修或85°闭环引导算法。
- 把当前700张重新命名为严格未见test，或根据检测结果挑选冻结组。
- 随机拆分连续帧、让同一物理零件跨split、删除失败或短组图片。
- 修改PLC、上位机或其他受保护检测仓库。
