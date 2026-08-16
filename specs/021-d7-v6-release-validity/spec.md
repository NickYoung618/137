# Feature Specification: D7 v6回退首版有效性诊断

**Feature Branch**: `main`

**Created**: 2026-08-17

**Baseline**: `d15703127f9b80351e42d2819f562553003802d2`

**Status**: Diagnostic decision complete; no runtime change

## User Scenarios & Testing

### User Story 1 - 区分数值有效和证据可审核 (Priority: P1)

首版负责人需要判断010组20帧的D7 v6原质量回退能否保留`measurementValid=true`，同时不能把
没有A/B原始边缘点和拟合线的结果说成“证据完整”。

**Why this priority**: Mac独立复验显示010+030共40/40有效且权威真值PASS，但010的20/20均为
`v6_original_quality`回退且`evidenceAuditStatus=unavailable`。数值质量和可视审核能力必须分开决策。

**Independent Test**: 对010的20条外置结果逐条核验v6原质量状态、有限量测、来源和审核字段，确认
`measurementValid`与`evidenceComplete`没有互相伪装。

**Acceptance Scenarios**:

1. **Given** v6两侧检测均通过原质量条件且五个业务量测均有限，**When** 新候选失败并回退，
   **Then** 可以保留技术数值有效，同时必须报告`evidenceComplete=false`和不可审核原因。
2. **Given** v6原质量状态失败或任一业务量测非有限，**When** 尝试回退，**Then** 不得恢复为有效。
3. **Given** 结果没有A/B原始点和拟合线，**When** 生成审核报告，**Then** 不得伪造两条边界或把一条尺寸线当作边缘证据。

### User Story 2 - 给出首版发布边界 (Priority: P1)

首版负责人需要一个不改变既有契约的可执行决策：哪些场景可以消费该数值，哪些场景必须继续阻断。

**Independent Test**: 发布矩阵分别列出技术检测、可视审核、精度声明和生产OK/NG，且每一项都有明确结论。

**Acceptance Scenarios**:

1. **Given** 010只有无真值重复帧，**When** 评估其20/20有效和静态重复性，**Then** 只能说明检测稳定性，不能说明绝对准确度。
2. **Given** 权威单图真值PASS，**When** 评估010其他零件/位置，**Then** 不得把单图精度外推为010逐帧精度。
3. **Given** `productionDisposition=not_evaluated`，**When** 首版交付，**Then** v6回退不得被解释为生产合格判定。

### User Story 3 - 保持安全门和Phi不变 (Priority: P2)

维护人员需要确认本次诊断不会通过放宽门限、真值调参或改变Phi来制造更高有效率。

**Independent Test**: 工作树差异只包含SpecKit 021文档；定向契约测试继续证明v6失败不恢复、
测量有效与证据完整相互独立。

### Edge Cases

- 只有一侧可审核D7证据时，应为`partial`，不能升级为`complete`。
- v6内部曾使用边缘点完成拟合，但输出没有保留这些点时，仍必须按交付结果标为`unavailable`。
- `technicalValid=true`不能替代`evidenceComplete=true`，也不能替代绝对精度或生产判定。
- 010中稳定但存在系统偏差的可能性不能由20帧重复性排除。

## Requirements

### Functional Requirements

- **FR-001**: MUST冻结Mac独立结论：010+030为40/40有效、权威真值PASS、Phi不变。
- **FR-002**: MUST逐条核验010的20条D7来源、回退路径、原质量状态、有限值和审核状态。
- **FR-003**: MUST追溯v6原质量状态具体由哪些图像门产生，并区分“计算时有边缘”与“交付时有可审核边缘”。
- **FR-004**: MUST明确`measurementValid`、`evidenceComplete`、绝对准确度和`productionDisposition`四个概念。
- **FR-005**: MUST给出“保留/拒绝/条件保留”的首版决策及风险边界。
- **FR-006**: MUST保持v6原质量门、当前D7/Phi算法、配置、Schema和运行时测试不变。
- **FR-007**: MUST禁止全局或定向降低门限、固定像素补偿、标称值选择和目标真值驱动调参。
- **FR-008**: MUST保留失败保护：`upstream != ok:dual_boundary_fit`或业务量测非有限时不得回退。
- **FR-009**: MUST不把010无真值重复性或权威单图真值外推为010绝对精度。
- **FR-010**: MUST规定首版报告同时呈现D7数值有效数和D7证据完整数。

### Key Entities

- **Measurement validity**: 检测器按既有质量逻辑产生有限D7数值的状态。
- **Evidence audit status**: A/B原始边缘点与拟合线能否被交付结果复核的独立状态。
- **v6 original-quality fallback**: 新候选失败后，仅复用原v6已通过结果的受控路径。
- **Release disposition**: 技术试用、可视审核、精度声明和生产判定四种不同使用权限。

## Success Criteria

- **SC-001**: 010的20/20记录逐条满足`ok:dual_boundary_fit`、五项有限值、明确v6来源和`unavailable`审核状态。
- **SC-002**: 失败保护定向测试100%通过，且没有门限或运行时代码差异。
- **SC-003**: 首版决策不会把20/20重复性称为准确度，也不会把无证据结果称为可审核。
- **SC-004**: 文档给出可执行双指标：`D7 measurementValid`与`D7 evidenceComplete`必须分别统计。
- **SC-005**: SpecKit analyze、`git diff --check`和文档范围审计通过。

## Assumptions

- Mac独立验证事实由用户冻结，本轮不重新读取Mac私有运行目录。
- 服务器外置010+030结果用于只读诊断，不进入Git。
- 初始发布仍是像素级技术检测交付，`productionDisposition`保持`not_evaluated`。
- 若业务要求每个有效数值都必须有A/B可视证据，应在后续增量中保留v6原始点，而不是放宽或改写有效性。
