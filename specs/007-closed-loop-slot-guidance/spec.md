# Feature Specification: 单真槽闭环旋转引导

**Feature Branch**: `003-a2-paired-notch-stability`

**Created**: 2026-08-15

**Status**: Specified and clarified

**Input**: 负责人确认真实任务是“检测唯一真槽后，输出到左下85°±5°目标的最短图像帧旋转引导，并支持重复拍照的无状态闭环”，不再把当前不在容差内误作检测失败或负样本。

## Clarifications

### Session 2026-08-15

- Q: 业务所称“负Y下半轴”与图像Y向下坐标如何对应？ → A: 角度数学使用图像`+Y`向下半轴为零位，顺时针为正；“负Y”仅作为设备/工件坐标别名，不反转图像角度符号。
- Q: PLC映射未确认时，可靠检测是否仍为有效结果？ → A: 是；图像帧引导量有效且`valid=true`，PLC/执行机械量单独阻塞并保持空值。
- Q: 已进入80°～90°时是否还输出到85°的微调？ → A: 否；这是闭区，引导量必须强制为0°且方向为`NONE`。

## User Scenarios & Testing

### User Story 1 - 可靠检测后给出最短旋转引导 (Priority: P1)

作为设备调试人员，我希望算法在外圆、唯一真槽和槽口几何可靠时，无论槽当前位于哪个象限，都能得到从当前方向到左下85°目标的最短有符号旋转量。

**Why this priority**: 这是槽姿态引导的核心业务价值；“当前不在位”不能再被误判为算法失败。

**Independent Test**: 对外圆和槽口几何已知的受控样例输入不同当前角，检查检测状态、最短环形旋转量、方向和有效性。

**Acceptance Scenarios**:

1. **Given** 当前角约`82.978°`且位于左下，**When** 生成引导，**Then** 检测状态为`DETECTED`、引导状态为`DETECTED_IN_POSITION`、修正量为`0°`、方向为`NONE`。
2. **Given** 当前角约`22.834°`，**When** 生成引导，**Then** 状态为`DETECTED_NEEDS_ADJUSTMENT`、修正量约`+62.166°`、方向为`CLOCKWISE`。
3. **Given** 当前角约`-158.111°`，**When** 生成引导，**Then** 状态为`DETECTED_NEEDS_ADJUSTMENT`、最短修正量约`-116.889°`、方向为`COUNTERCLOCKWISE`。
4. **Given** 当前角横跨±180°边界，**When** 计算修正，**Then** 必须使用`[-180,180)`环形最短差，不输出绕远路径。

---

### User Story 2 - 检测、在位与PLC权限独立 (Priority: P1)

作为上位机和PLC集成人员，我希望清楚区分“图像几何检测成功”、“是否需要调整”和“PLC是否已获准执行”，避免把映射阻塞伪装成检测失败。

**Why this priority**: 状态语义错误会使闭环无法运行，也可能让下游错误复用或丢弃有效引导量。

**Independent Test**: 使用同一份可靠几何结果，分别在PLC映射确认与未确认配置下检查图像引导和执行命令安全门。

**Acceptance Scenarios**:

1. **Given** 圆和唯一槽检测可靠但PLC映射未确认，**When** 输出结果，**Then** `valid=true`、`technicalStatus=succeeded`、图像引导量有值，而`mechanicalCorrectionDeg`/`plcCommand`为空且PLC状态明确为阻塞。
2. **Given** 外圆失败、真槽为0个或多个、槽壁精修失败或几何不可信，**When** 输出结果，**Then** `detectionStatus=DETECTION_FAILED`、`guidanceStatus=NOT_AVAILABLE`、`valid=false`，所有修正量保持空值且给出稳定失败码。
3. **Given** legacy、paired或multi-role配置，**When** 运行新版代码，**Then** 它们继续使用原结果契约和原有有效性规则。

---

### User Story 3 - 人工可审阅的闭环引导可视化 (Priority: P2)

作为现场负责人，我希望每张真实图的叠加图和表格直接显示检测成功、当前角、目标角、最短调整量、方向和是否已到位，而不是把“需调整”写成`FAIL`。

**Why this priority**: 人工能否正确看懂结果，直接决定真实样本审阅和后续闭环调试是否可信。

**Independent Test**: 对包含在位、需顺时针、需逆时针和检测失败的四个结果生成审阅包，检查叠加文案、JSON、CSV和联系表。

**Acceptance Scenarios**:

1. **Given** 可靠检测但需调整，**When** 渲染叠加图，**Then** 显示`DETECTED_NEEDS_ADJUSTMENT`和方向/数值，不显示`FAIL`。
2. **Given** 阴影候选被拒绝，**When** 渲染证据，**Then** 继续显示原始暗区、拒绝原因、唯一真槽紫色径向轴和亚像素槽壁支持/拒绝点。
3. **Given** 25张外置JPEG，**When** 重跑审阅工具，**Then** 产生25份逐图AUTO LabelMe、25张overlay、1张contact sheet及含闭环状态的JSON/CSV。

---

### User Story 4 - 无记忆污染的重拍闭环 (Priority: P2)

作为设备控制人员，我希望每次旋转后重新拍照都独立计算当前角和下一步引导，直到进入死区，不会复用上一帧的角度或命令。

**Why this priority**: 这是闭环安全性的基础，避免检测失败时仍按旧命令旋转。

**Independent Test**: 按“需调整 → 进入容差 → 下一帧检测失败”顺序输入三个独立任务，确认输出依次为有符号修正、0°和空值，不复用旧量。

**Acceptance Scenarios**:

1. **Given** 前一帧有效修正量，**When** 新帧检测失败，**Then** 新结果为`NOT_AVAILABLE`且所有修正/命令字段为空，不输出0°或旧值。
2. **Given** 新帧进入左下80°～90°闭区，**When** 计算引导，**Then** 独立输出0°和`NONE`，可作为闭环停止信号。

### Edge Cases

- 80°和90°必须包含在闭区内；浮点比较使用明确小容差，但不改变业务边界。
- 当前角可以在任意象限或坐标轴上；左下区域门只用于“已到位”判定，不用于判定检测是否成功。
- 修正差恰为180°时，必须使用契约的`[-180,180)`归一化，即确定性输出`-180°`和`COUNTERCLOCKWISE`。
- 检测失败与“检测成功但PLC映射阻塞”必须是可区分状态。
- 容差内的原始最短差可保留为诊断值，但对外图像引导量必须为0°。
- 结果超时、任务ID不匹配或帧哈希不匹配时，下游必须清除旧引导量。
- 图像帧顺时针不能直接等价为执行机顺时针；未完成现场映射时不得生成PLC命令。

## Requirements

### Functional Requirements

- **FR-001**: 系统 MUST 保留“外圆定位 → 原始暗区 → 唯一真槽过滤 → 亚像素槽壁/外圆交点 → 槽口中点径向”的现有复用链，不以新状态语义重写几何算法。
- **FR-002**: 系统 MUST 仅在外圆可信、恰好1个真槽通过、两侧亚像素槽壁及外圆交点可信时输出`detectionStatus=DETECTED`。
- **FR-003**: 当可信几何缺失或候选不唯一时，系统 MUST 输出`detectionStatus=DETECTION_FAILED`、`guidanceStatus=NOT_AVAILABLE`、`valid=false`和稳定失败码，不得填0或复用旧量。
- **FR-004**: 系统 MUST 以检测外圆圆心为原点、图像`+X`向右、图像`+Y`向下，以圆心向下的图像`+Y`射线为0°，顺时针为正，输出`currentAngleDeg∈[-180,180)`。
- **FR-005**: 系统 MUST 在契约中声明设备/工件坐标的“负Y下半轴”与图像坐标`+Y`下半轴是同一物理射线的不同命名，不得因命名反转符号。
- **FR-006**: 系统 MUST 将目标固定为`targetAngleDeg=85`、`toleranceDeg=5`，到位区域为左侧且下方/边界上的闭区`[80,90]`。
- **FR-007**: 系统 MUST 计算`correctionRawDeg=wrapTo180(targetAngleDeg-currentAngleDeg)`，正值表示图像帧顺时针，负值表示图像帧逆时针。
- **FR-008**: 当当前方向落在左下`[80,90]`闭区时，系统 MUST 输出`guidanceStatus=DETECTED_IN_POSITION`、`correctionDeg=0`、`rotationDirection=NONE`和`withinTolerance=true`。
- **FR-009**: 其他任何可靠检测方向 MUST 输出`guidanceStatus=DETECTED_NEEDS_ADJUSTMENT`、`correctionDeg=correctionRawDeg`、与符号一致的`CLOCKWISE`/`COUNTERCLOCKWISE`和`withinTolerance=false`。
- **FR-010**: 检测可靠时，结果 MUST `valid=true`、`technicalStatus=succeeded`且`error=null`，不得因为需要调整或PLC映射未确认而改为失败。
- **FR-011**: 新单真槽引导输出 MUST 使用独立版本结果契约；legacy、paired、multi-role和旧single-real-groove v1/v2 MUST 继续使用原契约和语义。
- **FR-012**: 新结果 MUST 同时输出`detectionStatus`、`guidanceStatus`、`currentAngleDeg`、`targetAngleDeg`、`toleranceDeg`、`correctionRawDeg`、`correctionDeg`、`rotationDirection`、`withinTolerance`、`imageFrameCorrectionDeg`以及质量置信度。
- **FR-013**: 当PLC映射未确认时，系统 MUST 保留有效`imageFrameCorrectionDeg`，但`mechanicalCorrectionDeg`和`plcCommand`必须为空，`plcExecutionStatus`必须为`BLOCKED_MAPPING_UNCONFIRMED`且列出阻塞项。
- **FR-014**: 图像引导与PLC执行必须分层；本功能不写PLC、不生成未确认地址/缩放/字节序，不改上位机。
- **FR-015**: 每帧 MUST 独立计算；新帧失败、超时或任务不匹配时不得返回0°或前帧修正量。
- **FR-016**: 审阅JSON、CSV和overlay MUST 使用新状态语义，不得将`DETECTED_NEEDS_ADJUSTMENT`标记为`FAIL`，并必须显示当前角、目标、最短修正、方向、是否到位和PLC权限。
- **FR-017**: 审阅包 MUST 保留唯一真槽紫色轴、原始暗区候选、阴影拒绝原因、槽壁内点/拒绝点和外圆证据。
- **FR-018**: 25张外置JPEG MUST 重新导出AUTO LabelMe、review JSON/CSV、overlay和contact sheet，并汇总`DETECTED_IN_POSITION`、`DETECTED_NEEDS_ADJUSTMENT`、`DETECTION_FAILED`及三种方向数量。
- **FR-019**: AUTO LabelMe MUST 继续标记为算法产物、非人工真值、禁止运行时作为truth；唯一人工样本只对自身提供开发参考差。
- **FR-020**: 角度误差和修正 MUST 使用环形差；不同当前角组不得混合原始角度计算动态极差。
- **FR-021**: 静态重复性 MUST 作为评价指标；只有明确同样品/同位置/同工况组时才计算，当前分组不明时保持`NOT_EVALUATED`。
- **FR-022**: 系统 MUST 通过契约和单元测试覆盖三个权威数值示例、闭区端点、±180°环绕、0/1/多真槽、圆/槽壁质量失败、旧模式兼容、失败不复用和PLC安全门。
- **FR-023**: 系统 MUST 保持现有单帧性能门限：同一服务器上完整单图P95不超过2.5秒、最大不超过4秒、串行吞吐不低于0.3张/秒、峰值内存不超过1.5 GiB；结果必须记录硬件和测量方法。
- **FR-024**: 代码、规格和脱敏证据可进入Git；原图、视频、压缩包、AUTO LabelMe实跑产物、叠加图和私有绝对路径 MUST 留在Git外。

### Key Entities

- **Detection State**: 外圆、唯一真槽、槽壁精修和槽口径向是否可靠，值为`DETECTED`/`DETECTION_FAILED`。
- **Image-frame Guidance**: 当前角、目标角、容差、原始最短差、死区后修正量、方向和引导状态。
- **PLC Execution Gate**: 图像引导到执行机命令的映射状态、阻塞原因、机械修正和PLC命令。
- **Review Record**: 每图检测/引导/PLC状态与可视几何证据。

## Success Criteria

### Measurable Outcomes

- **SC-001**: 三个权威示例逐一满足：`82.978°→0°/NONE`、`22.834°→约+62.166°/CLOCKWISE`、`-158.111°→约-116.889°/COUNTERCLOCKWISE`，数学误差不超过0.001°。
- **SC-002**: 所有受控当前角中，可靠检测的100%为`valid=true`；是否在位不改变检测有效性。
- **SC-003**: `[80,90]`边界及区间内样例100%输出0°/`NONE`，区间外样例100%输出最短非零环形修正及一致方向。
- **SC-004**: 0个或多个真槽、外圆失败和槽壁质量失败样例100%安全失败，修正量/机械量/PLC命令100%为空。
- **SC-005**: PLC映射未确认时，可靠检测的100%保留图像引导量且`valid=true`，同时100%不产生机械修正或PLC命令。
- **SC-006**: 25张现有JPEG实跑应得到`DETECTED_IN_POSITION=2`、`DETECTED_NEEDS_ADJUSTMENT=23`、`DETECTION_FAILED=0`；方向分布应为`NONE=2`、`CLOCKWISE=3`、`COUNTERCLOCKWISE=20`，若不一致必须逐图解释，不得篡改证据迎合预期。
- **SC-007**: 25张实跑产生25份AUTO LabelMe、25张overlay、1张contact sheet和完整JSON/CSV；可靠但需调整的图中不出现容差`FAIL`文案。
- **SC-008**: 新契约、CLI、批处理、可视化和失败分支测试全部通过，且历史legacy/paired/multi-role/single v1/v2测试无回退。
- **SC-009**: 完整单图P95≤2.5秒、最大≤4秒、串行吞吐≥0.3张/秒、峰值内存≤1.5 GiB；新状态/修正数学不得触发额外图像解码或重跑圆/槽检测链。
- **SC-010**: 当前25张无逐图真值和明确重复组时，准确度与静态重复性都明确为`NOT_EVALUATED`；观测稳定性不被包装为生产精度。
- **SC-011**: Git新增中不含图像、视频、压缩包、超大文件、人工真值或私有绝对数据路径。

## Assumptions

- 负责人已确认图像帧的角度基准、目标85°、±5°闭区和图像帧旋转正负，因此这些不再是业务BLOCKED项。
- “顺/逆时针”在本功能中首先指图像帧中的方向；相机安装与执行机实际方向映射仍待现场确认。
- 现有外圆、多暗区、真槽几何门和亚像素槽壁精修作为已建立基线，本轮主要修正状态、引导契约和审阅工具。
- 闭环控制器、相机触发、运动完成握手和超时停机属于上位机/PLC范围，本轮只保证每帧无状态引导结果可供后续闭环调用。
