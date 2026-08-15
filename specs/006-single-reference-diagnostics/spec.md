# Feature Specification: 单人工样板驱动的无真值诊断

**Feature Branch**: `003-a2-paired-notch-stability`

**Created**: 2026-08-15

**Status**: Implemented and locally verified

**Input**: 用户确认当前只有1张人工标注图，其他真实图像没有各自真值；现阶段以该标注图作为开发参考样板，但不把它的角度伪造成其他图像的真值。

## User Scenarios & Testing

### User Story 1 - 锁定唯一人工样板的证据边界 (Priority: P1)

作为算法开发人员，我希望把唯一人工外圆+真槽标注固化为带哈希和版本的开发参考，并明确它只能证明该图的人工/自动差值。

**Independent Test**: 输入人工审阅记录和同图自动对比记录，仅在图像、标注和拟圆源哈希一致时得到开发参考摘要。

**Acceptance Scenarios**:

1. **Given** 同图人工记录和自动对比均合法，**When** 生成参考摘要，**Then** 输出人工圆、槽角、自动差值、来源哈希和`DEVELOPMENT_REFERENCE_ONLY`范围。
2. **Given** 图像/标注/拟圆源哈希不一致，**When** 建立参考，**Then** 明确失败，不拼接不同样本。

### User Story 2 - 每张无真值图都能在LabelMe看到自动检测 (Priority: P1)

作为现场审阅人员，我希望每张真实图都有一份可用LabelMe打开的自动诊断JSON，能看出自动圆、槽口、槽中线、侧壁内点和拒绝点。

**Independent Test**: 对合法成功、fail-closed和路径异常样例导出诊断；每个Manifest条目有且只有一个诊断JSON，失败图不伪造0度或假几何。

**Acceptance Scenarios**:

1. **Given** 圆和单真槽几何有效，**When** 导出，**Then** LabelMe中的所有图形都使用`AUTO_`标签，且旗标明确`formal_truth=false`。
2. **Given** 算法对某图失败，**When** 导出，**Then** 仍生成记录并保留错误码，但不填角度0、不画虚构圆/槽。

### User Story 3 - 参考角差与真实误差分开 (Priority: P2)

作为质量人员，我希望批量表格可以显示每图检测值、85度诊断和“与参考样板观测差”，但绝不把后者命名为准确度误差。

**Independent Test**: 给定跨±180度的检测值，表格使用环形差并将其标为`OBSERVATION_ONLY`；无同图真值时准确度和静态重复性仍是`NOT_EVALUATED`。

## Edge Cases

- 人工参考图是BMP，批量图是JPEG，它们不得因画面相似而被当成同哈希真值。
- 批量图的姿态可能不同，与参考样板的角差只是观测差。
- 输入结果缺图、重复taskId、哈希不匹配、圆有效但槽失败、槽有效但PLC被阻塞。
- 槽口跨0度边界，必须使用环形中点/差值。
- 输出目录位于Git工作树内或与人工truth目录相同。

## Requirements

### Functional Requirements

- **FR-001**: 系统 MUST 将唯一人工标注样本输出为版本化开发参考，包含图像、标注、拟圆算法和运行时记录哈希。
- **FR-002**: 开发参考 MUST 显式声明`runtimeInputAllowed=false`、`productionAccuracyClaimed=false`且只对参考图本身有效。
- **FR-003**: 人工审阅与自动对比的图像、标注和拟圆源哈希不一致时 MUST 失败。
- **FR-004**: 每个Manifest真实图条目 MUST 导出且仅导出一个LabelMe自动诊断JSON和一行索引。
- **FR-005**: 自动诊断 MUST 使用不与人工truth标签重名的`AUTO_`标签，且设置`algorithm_generated=true`、`formal_truth=false`、`human_verified=false`、`runtime_input_allowed=false`。
- **FR-006**: 合法诊断 MUST 包含可用的自动外圆、槽口两交点、圆心至槽口中点轴、两侧内点/拒绝点及检测状态。
- **FR-007**: 检测失败时 MUST 保留错误码/阶段，不得用0度、参考角或上一张图弥补缺失几何。
- **FR-008**: 自动诊断JSON MUST 只引用外置原图，不嵌入图像二进制，不改写原图或人工标注。
- **FR-009**: 输出 MUST 位于Git工作树外，索引不得包含服务器或Mac绝对数据路径。
- **FR-010**: 每图 MUST 输出检测Y下半轴有符号角、象限、85度判定、错误码和与参考角的环形观测差；不可用时保持空值。
- **FR-011**: 与参考的角差 MUST 命名为`observedCircularDeltaToReferenceDeg`并标明`OBSERVATION_ONLY_NOT_ACCURACY_ERROR`。
- **FR-012**: 只有参考图本身可报告人工/自动差值；其他无真值图的准确度 MUST 为`NOT_EVALUATED`。
- **FR-013**: 静态重复性 MUST 继续要求明确同样品/同位置/同工况分组；当前25张分组不明时为`NOT_EVALUATED`。
- **FR-014**: 开发参考和自动诊断 MUST 只由离线工具消费，运行时算法不得导入它们或反向用参考角修正检测。
- **FR-015**: PLC映射未确认时，正式机械角 MUST 仍为空且`valid=false`。
- **FR-016**: 系统 MUST 有自动测试覆盖哈希不匹配、路径穿越、结果缺失/重复、成功/失败诊断、环绕角、truth标签泄漏和工作树内输出拒绝。

### Key Entities

- **Development Reference Profile**: 唯一人工样板的来源、人工几何、同图自动差值与使用边界。
- **Automatic LabelMe Diagnostic**: 一张无真值图的自动圆/槽几何及明确的非真值旗标。
- **Reference-Anchored Diagnostic Index**: 逐图检测值、85度诊断、观测差、错误码和产物哈希。

## Success Criteria

- **SC-001**: 唯一人工样板产生1份带完整来源哈希的开发参考，哈希异常样例100%拒绝。
- **SC-002**: 25张真实JPEG产生25份可打开的LabelMe自动诊断和25行索引，无图片复制或嵌入。
- **SC-003**: 所有自动诊断的人工验收旗标均为false，且不出现人工truth标签。
- **SC-004**: 合法图的自动圆、槽口、槽轴和侧壁证据100%与批处理JSON中的数值一致。
- **SC-005**: 失败记录中不出现0度或参考角填充，正式机械角继续为空。
- **SC-006**: 与参考的所有角差都使用环形差，且在JSON/CSV中100%标记为观测值而非准确度。
- **SC-007**: 当前25张的准确度和静态重复性仍明确为`NOT_EVALUATED`，唯一可报人工误差为参考图自身。
- **SC-008**: 全量测试、Schema、CLI、JSON和污染检查通过，Git不新增图像、标注真值、绝对数据路径或大文件。

## Assumptions

- 当前唯一人工标注与同图BMP开发对比记录已经存在于Git外。
- 25张JPEG没有各自的人工真值，且不猜测它们与参考BMP的物理姿态关系。
- 自动LabelMe文件是查看算法效果的诊断层，与独立人工truth目录分离。
