# Feature Specification: 真实槽与固定装置阴影源判别

**Feature Branch**: `027-groove-shadow-source-discrimination`

**Created**: 2026-08-18

**Status**: Draft

**Input**: Mac在`d776c4d`上完成700张A2真实回放与人工判读；必须区分“完整真实槽靠近固定装置阴影”与“真实槽壁/端点被阴影混合或遮挡”，逐图追踪候选生成、recognition、ambiguity、polar quality、refinement、source consistency和上游失败；不降低任何全局门限，不使用文件名、固定角度、人工标注或样本特判作为运行时输入。

## User Scenarios & Testing

### User Story 1 - 逐图解释近阴影失败 (Priority: P1)

算法开发人员需要在不改变检测结果的前提下，对每张失败图明确记录失败发生在候选生成、几何识别、多候选歧义、全局极坐标质量、双壁精修、壁源一致性还是上游外圆，并对每个候选保留来源证据。

**Why this priority**: 700张已观察数据中的错误码只表示终止阶段，不能区分完整真槽与阴影混合槽；先建立可审计证据才能避免盲目调阈值。

**Independent Test**: 对冻结的207张失败索引与700张结果流做只读追踪，每行都能唯一匹配图像SHA、终止阶段、候选数量与可用来源证据，且不改变原结果。

**Acceptance Scenarios**:

1. **Given** 一张没有生成真实槽候选的图像，**When** 生成诊断，**Then** 结果明确标记`candidate_generation`并保留原始阈值假设与被拒绝run证据。
2. **Given** 多个候选已通过粗几何识别，**When** 进行追踪，**Then** 每个候选都有独立的宽度、对比度、径向深度、双边支持、连续性、端点和壁源证据。
3. **Given** 外圆或全局质量门先失败，**When** 生成诊断，**Then** 不伪造未执行的槽候选或壁源结论。

---

### User Story 2 - 区分完整近阴影与混合遮挡 (Priority: P1)

在单张图像中，系统需要只根据图像和物理几何证据，区分`REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW`、`REAL_GROOVE_SHADOW_MIXED_OR_OCCLUDED`与证据不足。只有唯一完整真槽且所有竞争候选都有可靠的非真槽证据时，才可继续姿态链。

**Why this priority**: 完整真槽靠近阴影不等于遮挡，但将混合阴影误当真槽会产生危险姿态。

**Independent Test**: 用合成与已有独立人工语义样例验证：完整双壁、外圆肩部端点和同源证据齐全时可形成唯一可用真槽；任一壁/端点混入阴影、遮挡或多个候选仍然同等可信时必须fail-closed。

**Acceptance Scenarios**:

1. **Given** 真实槽两壁完整、独立且端点均连接物理外圆肩部，附近阴影候选不能通过同样的物理双壁与同源门，**When** 做来源裁决，**Then** 唯一真槽可被选中，所有候选的通过/失败证据完整保留。
2. **Given** 真槽任一壁或开口端点被阴影遮挡或拟合段含阴影源，**When** 做来源裁决，**Then** 分类为`REAL_GROOVE_SHADOW_MIXED_OR_OCCLUDED`或证据不足，姿态与PLC字段全部为空。
3. **Given** 两个候选都通过完整物理证据，**When** 做唯一性裁决，**Then** 系统保持歧义失败，不得依据分数、文件名、固定角度或人工类别强选。
4. **Given** `polar_score`仍未通过原质量门，**When** 局部真槽证据完整，**Then** 系统只记录分解诊断并继续fail-closed，不绕过或降低原全局质量门。

---

### User Story 3 - 物理分离的冻结验收 (Priority: P2)

评测人员需要用与已观察700张物理分离的新零件组做回归，分别报告完整近阴影可安全放行、继续拒绝、混合/遮挡全部拒绝和其他阶段失败的数量。

**Why this priority**: 700张数据已被观察且物理分组不可靠，只能用于诊断，不能证明泛化或准确率提升。

**Independent Test**: 冻结新零件manifest和人工审核后，核对物理零件无交集、配置/代码SHA不变、失败安全字段全空、混合/遮挡样本100%拒绝。

**Acceptance Scenarios**:

1. **Given** 新验收组与700张已观察数据无物理零件交集，**When** 运行冻结候选，**Then** 报告逐类计数、失败阶段、质量证据、静态重复性和耗时，不用验收结果反向调参。
2. **Given** 新零件验收尚未完成，**When** 发布开发报告，**Then** 报告必须标记验收阻塞，不宣称准确率提升、不开启生产默认、不授权PLC。

### Edge Cases

- 阴影与真槽角度很近但像素源仍可分，不得以角度距离直接屏蔽。
- 阴影横跨一条真槽壁或开口肩部，即使宏观槽中心正确也必须拒绝。
- 真槽与阴影候选分数接近或顺序翻转，来源裁决必须不变。
- 全局`polar_score`低但局部双壁完整，当前只允许诊断，不允许越过原门。
- 候选数为0、1、2、3或超过容量上限时，诊断必须完整且容量溢出时必须安全失败。
- 外圆无唯一族或外圆质量不足时，不生成真槽/阴影语义结论。
- 任一证据非有限、缺失或Schema版本不匹配时，不得放行姿态。

## Requirements

### Functional Requirements

- **FR-001**: 系统 MUST 对每张图记录版本化终止阶段，至少区分候选未生成、recognition拒绝、多候选歧义、`polar_score`质量拒绝、refinement失败、source-consistency失败、外圆/上游失败和有效。
- **FR-002**: 系统 MUST 对每个径向/极坐标候选记录候选来源、角宽、径向深度、对比度、成对边支持、轮廓连续性、宽度稳定性和外圆肩部连接证据。
- **FR-003**: 对进入物理精修的每个候选，系统 MUST 独立记录两壁拟合、两壁端点、外圆交点、径向覆盖和两壁像素源一致性证据；缺失不得用推测值填充。
- **FR-004**: 运行时诊断 MUST 使用三态来源分类：`REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW`、`REAL_GROOVE_SHADOW_MIXED_OR_OCCLUDED`、`INDETERMINATE`，并同时输出证据通过项、失败项和是否允许继续姿态链。
- **FR-005**: `REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW` MUST 同时要求两壁独立完整、端点连接物理外圆肩部、两壁来源一致、唯一真槽存活，且所有竞争候选均有明确的物理精修或来源失败证据。
- **FR-006**: 任一真槽壁/端点遮挡、拟合段混入阴影源、多个候选仍同等可信或证据不足 MUST fail-closed。
- **FR-007**: 来源裁决 MUST 只使用当前单张图像与几何证据，MUST NOT 读取文件名、路径、sampleId、人工标注、人工评审类别、前帧、固定角度白名单或候选顺序。
- **FR-008**: 系统 MUST NOT 降低或绕过现有ambiguity、groove recognition、refinement、`min_polar_score`或source-consistency门；原门和新来源裁决的执行顺序 MUST 版本化。
- **FR-009**: `polar_score`低的完整近阴影样本在本功能中 MUST 仅获得分解诊断，不得因局部分类被放行。
- **FR-010**: 来源判别必须为严格默认关闭的版本化配置；关闭时既有运行路径和结果必须兼容，新物理零件验收前不得进入生产默认。
- **FR-011**: 系统 MUST 保持单张图像输入、既有坐标/角度/目标区间契约和既有外圆边族唯一性契约，不引入多拍依赖。
- **FR-012**: 任一歧义、混合/遮挡、证据不足、上游失败或质量门失败时，当前角、方向、修正量、机械量和`plcCommand` MUST 全部为null，不得复用旧值。
- **FR-013**: 新诊断 MUST 为有界摘要并可由Schema验证；完整逐像素/逐采样证据和代表性叠加图只能写入Git工作树外。
- **FR-014**: 700张已观察数据 MUST 仅用于诊断、开发和回归对照，MUST NOT 被宣称为unseen acceptance或用于反复调整全局阈值。
- **FR-015**: 最终验收 MUST 使用与700张已观察数据物理零件分离的新组，冻结配置和代码后一次性解封，分开报告完整近阴影、混合/遮挡与其他失败。
- **FR-016**: 系统 MUST 提供与原始图像SHA、配置SHA、算法版本和证据Schema绑定的逐图诊断报告与代表性叠加图索引。
- **FR-017**: 实现和验收 MUST 不修改PLC/HMI、不授权PLC、不合并`main`、不读取或运行sealed part-006。
- **FR-018**: 开发报告 MUST 显式列出每个失败阶段数量、完整近阴影中允许继续/继续拒绝数、混合/遮挡拒绝数、数据物理分离状态和未完成验收阻塞。

### Key Entities

- **Failure Trace**: 一张图的图像SHA、终止阶段、上游状态、候选数量、质量失败项和安全输出状态。
- **Candidate Source Evidence**: 单个候选的径向/极坐标来源、几何、双壁、端点、外圆肩部连接和像素源一致性证据。
- **Groove Shadow Disposition**: 三态诊断类别、支持/反对证据、唯一选中候选和姿态链放行状态。
- **Observed Diagnostic Cohort**: 已观察700张的不可作为unseen acceptance的冻结索引、结果和人工语义证据。
- **Independent Acceptance Cohort**: 与Observed Cohort物理零件无交集、冻结后一次性解封的新零件组。

## Success Criteria

### Measurable Outcomes

- **SC-001**: 冻结`failure-index.csv`的207行与700张结果流100%按图像SHA唯一匹配，逐图诊断无遗漏、重复或终止阶段不一致。
- **SC-002**: 46张`GROOVE_RECOGNITION_AMBIGUOUS`全部记录所有accepted候选（至少两个、最多三个）及每个候选的物理精修/来源证据；未运行的证据明确标为未评估。
- **SC-003**: 20张仅`polar_score`失败样本100%报告原始分数、锁定阈值、局部真槽证据可用性和附近竞争候选证据，且结果仍全部fail-closed。
- **SC-004**: 独立人工标记为`REAL_GROOVE_SHADOW_MIXED_OR_OCCLUDED`的新零件样本100% fail-closed，所有姿态、方向、机械和PLC字段为null。
- **SC-005**: 对新物理零件中人工标记为`REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW`的样本，报告安全放行数、继续拒绝数及每个结论的唯一物理证据；不设置为了“提升率”而必须放行的最小数量。
- **SC-006**: 修改前后配置对比证明ambiguity、groove recognition、refinement、`min_polar_score`、source-consistency的原门限值100%不变。
- **SC-007**: 合成测试中图像/候选旋转、候选重排、候选ID改名和亮度有界变换不改变来源类别与唯一性结论。
- **SC-008**: 功能关闭时既有全量测试、结果Schema和026真实回归无变化；功能开启时聚焦测试、新Schema、失败安全契约和单图热态P95不高于2.5秒全部通过。
- **SC-009**: 新验收manifest与700张已观察组的物理sampleId交集为空，且不包含sealed part-006。
- **SC-010**: 在新物理零件验收完成前，所有报告的生产准确率结论、生产默认开启和PLC授权均为未允许。

## Assumptions

- 700张结果流、207张失败索引和 contact sheet 只是已观察诊断证据；其物理零件分组未被独立建立。
- 当前上传包没有提供A/B语义的逐图人工标签，因此已观察700张不能用来计算A/B分类准确率。
- Mac回放配置仅开启026外圆边族，并未开启已审核的候选物理歧义解析与双壁源一致性；本功能先补齐可解释证据，不把配置差异误当新阈值根因。
- 新物理零件数据需由数据持有者提供并冻结分组；在此之前只能完成开发与回归，不能完成独立验收。

## Out of Scope

- 修改PLC/HMI、确认机械映射或输出可执行PLC命令。
- 降低全局质量、识别、歧义、精修或壁源门限。
- 固定屏蔱上方角区、使用历史固定装置角度模板或样本白名单。
- 使用多拍、前帧或人工标注作为运行时输入。
- 将已观察700张声明为生产准确率或最终验收证据。
