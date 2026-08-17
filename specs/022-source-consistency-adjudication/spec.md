# Feature Specification: 真槽同源性误拒裁决

**Feature Branch**: `022-source-consistency-adjudication`

**Created**: 2026-08-17

**Status**: Implemented Candidate — awaiting Mac independent replay; not authorized for main

**Input**: 145独立长弧真值已证明AUTO完整槽几何角误差为`0.013368°`，但现有运行时仅因两壁对比度不对称而拒绝。修正该类洁净同源双壁误拒，同时保持混合fixture边、遮挡、多解和上游失败全部fail-closed。

## Clarifications

### Session 2026-08-17

- Q: 是否直接放宽现有`0.12`对比度门？ → A: 否。原门和原始裁决完整保留，另建默认关闭、版本化的实验裁决。
- Q: 哪些证据可作正反例？ → A: 145是独立像素/外圆角度正例；147只是同源双壁与端点语义/像素正例；part-019是“一真壁+一fixture边”混合负例；其他无人工真值帧不用于准确率声明或门限选择。
- Q: 裁决通过后是否可写PLC？ → A: 否。它只能在显式实验配置下恢复图像帧检测/引导字段，PLC/HMI仍阻断。
- Q: 147外圆真值是否为145运行时修正的前置？ → A: 否。147可后续扩充角度真值，但不阻塞145已证实的误拒根因修正。

## User Scenarios & Testing

### User Story 1 - 洁净完整槽恢复运行时图像引导 (Priority: P1)

算法工程师在显式开启实验裁决时，能将“只因对比度不对称失败，但其他同一方形开口结构证据一致”的候选恢复为有效图像姿态，输出当前角和到85°目标的最短有符号调整量。

**Why this priority**: 145已有独立真值证明候选几何正确，现有失败是运行时初版输出的直接阻塞。

**Independent Test**: 对冻结145记录与同图真值离线回放；实验开关开启后应得到`DETECTED_NEEDS_ADJUSTMENT`、约`29.578394°`当前角和约`+55.421606° CLOCKWISE`，且候选角对人工角误差仍为`0.013368°`量级。

**Acceptance Scenarios**:

1. **Given** 原同源性只失败`edge_contrast_asymmetry`、其他原始检查全过且独立结构证据过门，**When** 实验裁决显式开启，**Then** 保留原拒绝证据，同时输出独立的有效裁决并继续计算图像姿态。
2. **Given** 同一输入，**When** 配置缺失或关闭，**Then** 输出与现有基线一致，仍`GROOVE_SOURCE_INCONSISTENT`/`valid=false`。
3. **Given** 裁决恢复了图像姿态，**When** 查看集成输出，**Then** PLC命令和机械映射仍为null/blocked。

---

### User Story 2 - 混合边、遮挡和多解保持失败关闭 (Priority: P1)

现场质量人员需要确保，修正洁净槽误拒时不会将真槽一侧与fixture阴影边组成伪槽，也不会从遮挡的单壁中补造完整开口。

**Why this priority**: 稳定假阳性会输出错误旋转指令，风险高于保守拒绝。

**Independent Test**: part-019已人工确认混合边的20帧在开启实验裁决后仍全部拒绝；合成遮挡、缺壁、多解、多重失败和证据不全输入均无角度。

**Acceptance Scenarios**:

1. **Given** part-019式真壁+fixture边混合配对，**When** 实验裁决开启，**Then** 仍返回`GROOVE_SOURCE_INCONSISTENT`且所有引导字段为null。
2. **Given** 原同源性失败不只一项、任一必需证据缺失或非有限，**When** 裁决，**Then** 不得改写拒绝。
3. **Given** 只有一条可见真壁或存在多个局部开口解，**When** 检测，**Then** 继续`PARTIALLY_OBSERVED`或`AMBIGUOUS`，不输出姿态。

---

### User Story 3 - 裁决证据可审计且不污染真值 (Priority: P2)

算法工程师能在每帧诊断中区分原同源性判定、新裁决的有效状态、所用版本/数值证据和最终检测状态；人工标注只进入离线评估，不进入运行时。

**Why this priority**: 同一帧中“原门失败”与“二级裁决通过”必须同时可见，否则无法审计误拒修正。

**Independent Test**: 输出Schema强制保留original/effective状态、检查列表、失败理由和八项安全策略；扫描运行时代码证明不读LabelMe、imageId、sampleId或固定角。

**Acceptance Scenarios**:

1. **Given** 裁决任何结果，**When** 查看diagnostics，**Then** 原`sourceConsistency.status/metrics/checks/failedChecks`逐项保留，新裁决独立输出。
2. **Given** 人工145/147和part-019证据，**When** 运行生产检测函数，**Then** 不传入或读取任何人工坐标、文件名或样品身份。
3. **Given** 默认配置，**When** 运行旧legacy/paired/multi-role/single路径，**Then** 输出不因022而变化。

### Edge Cases

- 对比度差刚好在原0.12边界；原门必须按原规则执行，不改比较符。
- 二级结构证据位于自身版本化边界；比较符、单位和有限性必须有契约测试。
- 原`failedChecks`顺序被改变或出现未知检查；不得把“看起来只有contrast”当作可裁决。
- 原判定已accepted；不需二级override，应保留`NOT_NEEDED`而非重复升权。
- 候选几何通过但图像过期、圆失败或顶层质量门失败；二级裁决不得越过其他阶段。
- 候选角已在`[80,90]`死区；只有检测与几何都有效时才输出0°，失败不能填0。

## Requirements

### Functional Requirements

- **FR-001**: 系统 MUST 提供版本化的双壁同源性二级裁决，配置缺失或关闭时不执行且不改变现有输出。
- **FR-002**: 二级裁决 MUST 只消费当前图像检测产生的数值几何/剖面证据；MUST NOT 读取人工LabelMe、真值坐标、imageId/sampleId、文件名或固定图像角。
- **FR-003**: 裁决候选 MUST 要求原状态为`rejected`且原失败集合精确为`edge_contrast_asymmetry`一项；任一多失败、未知失败或证据结构错误 MUST 保持拒绝。
- **FR-004**: 裁决 MUST 要求梯度对称、归一化剖面差/相关、径向覆盖、端点结构等所有非contrast原检查通过。
- **FR-005**: 裁决 MUST 额外使用版本化且有合成正反例的严格槽口端点结构一致性门；不得放宽现有`0.12`对比度门。
- **FR-006**: 裁决 MUST 输出`NOT_EVALUATED/NOT_NEEDED/REJECTED/ACCEPTED_OVERRIDE`之一，并输出原状态、有效状态、配置/门限版本、每项check、数值、门限和failedChecks。
- **FR-007**: `ACCEPTED_OVERRIDE` MUST 只将本次同源性有效状态设为accepted，MUST 原样保留原`sourceConsistency`payload，不得改写其status/metrics/checks/failedChecks。
- **FR-008**: 当且仅当物理圆、真槽唯一性、双壁精修、二级裁决和其他顶层质量门全部通过时，系统 MAY 输出`detectionStatus=DETECTED`和图像当前角/修正量。
- **FR-009**: 恢复的图像引导 MUST 沿用`image-y-down-clockwise-signed/1`：下半轴0°、顺时针为正、`wrap180`、目标85°和`[80,90]`死区。
- **FR-010**: 运行时valid只表示当前实验检测/几何链有效；PLC机械映射、命令和写入 MUST 继续blocked/null。
- **FR-011**: part-019已确认混合边负例 MUST 在启用二级裁决后仍100%无有效姿态；不得用样品坐标或角度特判实现。
- **FR-012**: 单壁可见、fixture混合、0候选、多候选、物理圆/精修失败或证据缺失 MUST fail-closed，所有引导数值为null而非0。
- **FR-013**: 145实验回放 MUST 保留原contrast拒绝证据，二级裁决通过后输出当前角/有符号修正；离线对独立人工角的绝对误差 MUST 继续`<=5°`。
- **FR-014**: 147 MAY 用于双壁同源与端点回归，但在外圆真值缺失时 MUST NOT 产生角度准确率结论。
- **FR-015**: 默认配置、legacy、paired_notches、multi-role和未开启的single路径 MUST 不回归；新配置必须只允许`single_real_groove`。
- **FR-016**: 运行时裁决 MUST 有有限值、字段完整、未知字段、边界比较和状态一致性Schema/单测；非法配置在图像解码前失败。
- **FR-017**: 真值只用于Git外离线验收；任何人工坐标、图片、JSONL或外置报告 MUST NOT 进入Git或运行时配置。
- **FR-018**: 本增量 MUST 在新功能分支默认关闭，必须经Mac真实原始BMP独立回放与人工证据裁决后才可讨论main；本规格不授权main合并或PLC/HMI修改。

### Key Entities

- **OriginalSourceConsistency**: 现有双壁对比、梯度、剖面、径向覆盖和端点结构原始判定，始终不可改写。
- **SourceConsistencyAdjudication**: 二级裁决状态、证据完整性、版本化检查、失败理由与有效状态。
- **EffectiveGrooveRefinement**: 在不改写原证据前提下，决定是否可继续计算槽口中点和图像引导的有效精修状态。
- **TruthBoundEvaluation**: 通过图像SHA把运行时候选与145正例/part-019负例离线关联，不进入运行时。

## Success Criteria

### Measurable Outcomes

- **SC-001**: 配置缺失或关闭时，现有全量测试和重点基线输出100%不回归。
- **SC-002**: 所有合成的contrast-only洁净槽均可在显式开启后得到`ACCEPTED_OVERRIDE`；多失败、缺证据、非有限和边界不过样例100%拒绝。
- **SC-003**: part-019已确认混合边的20/20帧在开启新裁决后仍`valid=false`、角度/修正/PLC全null。
- **SC-004**: 145在显式开启后能产生非PLC图像引导，当前角对正式人工真值绝对误差`<=5°`，且原contrast拒绝payload仍完整可审计。
- **SC-005**: 147可用于同源双壁运行时回归，但评估报告100%不输出最终角度准确率。
- **SC-006**: 遮挡、单壁、0/多候选、物理圆失败、精修失败和其他顶层质量失败的聚焦测试100%保持fail-closed。
- **SC-007**: 每个裁决输出100%含原/有效状态、版本、数值检查和失败理由；Schema拒绝状态与字段矛盾。
- **SC-008**: 开启裁决的新增计算对单图P95耗时影响`<=5 ms`，不新增大图复制或第二次图像解码。
- **SC-009**: 服务器聚焦/全量、全部Schema、Mac原始BMP配对回放、diff/大文件/绝对路径污染门全通过，才可将候选交给后续评审。
- **SC-010**: 本增量完成后仍默认关闭、仅功能分支，main和PLC/HMI零变更，不据单图声明数据集准确率。

## Assumptions

- 145和147的人工语义确认及独立槽壁/端点点标保持有效；145长弧报告是当前唯一正式单图角度真值。
- part-019的混合边人工裁决保持有效，可作稳定假阳性负例，但不用其固定角或坐标做运行时规则。
- 新裁决在得到更多物理零件独立真值前保持development-only和默认关闭。
- 双拍框架仍保留，但现场旋转参数未确认，不是022的运行时输出前置。

## Out of Scope

- 不修改原`0.12`对比度门或其仟020同源性门限。
- 不使用深度学习，不读取LabelMe作运行时输入，不读sealed part-006调参。
- 不合并main，不修改PLC/HMI地址、缩放、字节序或写入逻辑。
- 不将单张145的`0.013368°`扩展为数据集准确率或生产精度声明。
