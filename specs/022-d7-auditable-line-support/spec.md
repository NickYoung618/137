# Feature Specification: D7可审核直边支持

**Feature Branch**: `main`

**Created**: 2026-08-17

**Baseline**: `0658edad66f2ff2abba296845452d0b45fa15142`

**Status**: Implemented; awaiting final repository gates

## User Scenarios & Testing

### User Story 1 - 直观看清D7两条物理直边 (Priority: P1)

审核人员打开预览图或LabelMe预测时，需要明确看到窄颈上下两条实际直边A/B是直线，而不是把短支持段
误认为曲线。D7仍是这两条平行直边之间的公法线距离；证据不足时用局部放大改善可见性，不延长轮廓。

**Why this priority**: 当前581、582、981的A/B数学上是直线，但只显示约一个局部扫描条带，无法直观审核
它们是否沿窄颈实际直边贴合。

**Independent Test**: 对代表帧生成预览和LabelMe，A/B均为两点直线；线段只覆盖实际边缘支持的连续直边，
从公法线附近朝窄颈延伸，并在圆角、圆弧或证据中断前停止。

**Acceptance Scenarios**:

1. **Given** 窄颈方向存在成对边缘支持，**When** 输出审核几何，**Then** A/B线段严格裁到同语义原始支持的投影范围。
2. **Given** 圆柱侧是圆弧/连接圆角，**When** 输出A/B，**Then** 线段不得向圆柱侧穿过该非直边区域。
3. **Given** 中途没有合格边缘支持，**When** 确定显示范围，**Then** 不得为了视觉完整而越过缺口外推。
4. **Given** A/B与公法线同时显示，**When** 人工审核，**Then** 三者标签、颜色和语义可以明确区分。
5. **Given** 全图缩放后有限支持段难以辨认，**When** 生成预览，**Then** 提供D7局部放大但不改变LabelMe原坐标或线段范围。

### User Story 2 - v6回退保留真实但非等价的审核证据 (Priority: P1)

010使用v6原质量回退时，审核人员希望看到v6当时实际使用的单梯度边缘点和拟合线，而不是完全没有A/B；
同时系统不能把它们伪装成当前“双跃迁中点”物理边界。

**Why this priority**: 010的20帧数值有效但A/B证据缺失，无法判断v6选择了哪一层。

**Independent Test**: 构造v6原质量通过结果，输出两侧真实raw/inlier points和有限线段，但保持
`evidenceComplete=false`、`evidenceAuditStatus=unavailable`并标记`REVIEW`；v6失败时不输出审核线。

**Acceptance Scenarios**:

1. **Given** v6两侧原边界检测通过，**When** current-capture回退，**Then** 输出v6实际点和拟合直线作为review-only几何。
2. **Given** v6证据属于单梯度边缘，**When** 生成正式证据状态，**Then** 不得升级为与paired-transition等价的完整证据。
3. **Given** v6任一侧失败或证据不完整，**When** 输出审核报告，**Then** 不得伪造缺失边界。

### User Story 3 - 保持测量结果与检测率不变 (Priority: P1)

负责人需要确认本轮只是补齐可审核几何，不改变已验收的D7/Phi数值、质量门和100帧技术完成率。

**Independent Test**: 对同一输入比较修改前后的JSONL，registration、D7、Phi有效状态和数值逐帧一致；
唯一权威真值仍满足D7不超过2px、Phi直径不超过1px。

### Edge Cases

- 更远处虽有强单梯度边缘，但与paired中点不是同一光学层时，不得用它撑长正式A/B。
- 支持点落在圆弧上但偶然接近拟合线时，不得仅凭距离纳入直边显示。
- 线段端点必须来自支持范围在拟合直线上的投影，不得来自图像边界或标称长度。
- v6 review线可以显示，但不能进入正式`fittedGeometry.boundaries`或证据完整性判断。
- 无目标真值的100帧只能验证回归和重复性，不能生成新的绝对精度结论。

## Requirements

### Functional Requirements

- **FR-001**: D7 MUST定义为窄颈上下两条实际平行直边之间的公法线距离，不得改成圆弧、角点或整段轮廓尺寸。
- **FR-002**: 正式A/B拟合几何MUST使用严格直线方程，显示端点MUST共线。
- **FR-003**: 正式A/B显示范围MUST由实际双跃迁边缘支持决定，只沿窄颈方向显示，不得穿过圆柱圆弧或末端圆角。
- **FR-004**: 系统MUST区分原始边缘点、拟合直线和公法线尺寸标注，三类对象不得互相冒充。
- **FR-005**: 系统MUST保存v6回退实际使用的两侧raw/inlier points、拟合线方程和有限支持段。
- **FR-006**: v6单梯度证据MUST标为review-only且语义不等价；不得使`evidenceComplete`变为true。
- **FR-007**: v6原质量或证据不完整时MUST保持现有失败/不可审核状态，不得补画缺失线。
- **FR-008**: renderer与LabelMe MUST明确区分正式A/B、公法线和v6 REVIEW A/B，并保持原图坐标。
- **FR-008a**: 预览MUST提供D7有限支持段局部放大和A/B标签；放大只改变显示比例，不得改变几何坐标。
- **FR-009**: MUST保持D7数值选择、D7质量门、Phi算法/数值、配置和Schema不变。
- **FR-010**: MUST禁止使用标称值、文件名、固定像素补偿或目标真值决定线段和候选。
- **FR-011**: MUST验证唯一权威真值、010/030/050代表帧及5组100帧状态/数值/重复性回归。
- **FR-012**: 新旧审核图、BMP、JSONL和运行输出MUST留在仓库外，不得进入Git。

### Key Entities

- **Paired boundary support**: 暗边缘带外/内两次相反梯度及其中点构成的实际直边证据。
- **Supported fitted segment**: 只覆盖连续合格支持范围、端点严格投影到拟合直线的有限线段。
- **Measurement annotation**: A/B之间的公法线连接线及D7像素值，不是物理边缘。
- **Legacy review boundary**: v6单梯度检测实际点和拟合线，仅供REVIEW，不等价于正式物理边界。

## Success Criteria

- **SC-001**: 581、582、981的正式A/B均为两点直线，端点到各自线方程距离小于数值精度容差，且不向圆柱侧越过公法线。
- **SC-002**: 正式线段的每个显示端点均落在同语义paired支持点投影范围内；缺少同语义支持时不延长，并以局部放大协助审核。
- **SC-003**: 010代表帧能输出v6真实review点/线，同时继续报告证据不可用；失败v6测试100%不伪造证据。
- **SC-004**: 权威真值继续满足D7误差不超过2px、Phi直径误差不超过1px。
- **SC-005**: 5组100帧execution、registration、D7、Phi有效状态不低于当前100/100，正式数值和Phi逐帧不发生本轮证据显示导致的改变。
- **SC-006**: 全套测试、compileall、Schema、SpecKit analyze、diff和大文件审计全部通过。

## Assumptions

- 017权威人工模板和BMP继续是唯一运行时参考。
- 581/582人工D7-A/B只用于离线方向/位置审核，不参与运行时范围选择。
- 现有正式paired-transition点云是本轮唯一允许决定正式A/B显示范围的同语义证据；更远单梯度层只可作为被拒绝诊断。
- 初始技术版本的010条件保留规则继续有效。
