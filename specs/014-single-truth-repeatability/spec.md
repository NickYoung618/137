# Feature Specification: 单一真值与无标注重复性诊断

**Feature Branch**: `main`

**Created**: 2026-08-15

**Status**: In progress

## Scope

孔2目前只有一张负责人确认的LabelMe真值。该真值只负责定义尺寸7与Phi12.2的物理边界及
单图像素精度；其他normal图片没有尺寸真值，只能用于检测状态、图像质量证据、同一样品多帧
重复性和回归诊断。本增量提供显式manifest驱动的离线研究工具，不修改孔2运行时检测算法、
配置、Schema或质量门。

## Clarifications

- 人工真值只有一张，不再要求追加标注。
- 无标注帧不得自动变成伪真值，也不得支持逐图像素精度结论。
- 每个样品的采集帧关系必须由外置manifest明确给出；工具不得仅凭文件名猜测物理样品。
- defective始终独立观察，不能进入normal接受指标。

## User stories

### US1 - 唯一真值仍是独立精度门（P1）

离线工具读取已有单图验收报告，而不是目标LabelMe，报告尺寸7与Phi的像素误差及PASS/FAIL。
运行时检测入口不接收目标真值。

### US2 - 无标注帧用重复性发现疑似选边（P1）

用户用外置manifest明确每帧的population、role和captureGroupId。工具对同一样品多帧分别统计
尺寸7长度、Phi直径的有效数、中位数、范围、MAD及逐帧相对组中位数偏差；同时把静态重复性
作为明确评价指标，报告均值、样本标准差、6σ和极差，但不得把偏差称为真实误差或自动更改
有效状态。

### US3 - normal、holdout和defective证据严格隔离（P1）

报告按population和role分别统计注册、尺寸7、Phi、双特征有效及失败原因。holdout只有在调用者
显式提供结果后才进入报告；defective不得汇入normal。

### US4 - 候选来源与恢复路径可追溯（P2）

每个重复组汇总sourceDetector、recoveryPass和失败原因，使弱边缘、回退或跨带失败能与数值跳变
一起审核。

## Functional requirements

- **FR-001**: MUST 新增通用离线CLI，接受可重复`--jsonl`、外置`--manifest`、已有
  `--truth-report`及外置`--output`。
- **FR-002**: MUST NOT读取目标LabelMe或原图，不得运行或修改检测算法。
- **FR-003**: manifest MUST为每条记录提供唯一fileName、population、role、captureGroupId；缺失、
  重复或未映射必须失败。
- **FR-004**: MUST按`population + role`分开统计，不输出混合normal/defective验收总数。
- **FR-005**: MUST按`population + captureGroupId`统计两项量测的count、median、range、MAD和逐帧
  median deviation。
- **FR-005a**: MUST为每项输出`staticRepeatability`，至少包含有效帧数、要求帧数、均值、样本
  标准差、6σ、极差和`EVALUATED/INCOMPLETE`；默认要求同组20个有效帧且允许显式配置，没有
  外部工程门限时不得输出PASS/FAIL。
- **FR-006**: MUST把重复性数值标记为diagnostic，不得解释为真实尺寸误差、mm或生产OK/NG。
- **FR-007**: MUST汇总每项的sourceDetector、recoveryPass和failureReason。
- **FR-008**: MUST保留唯一真值报告的哈希、误差、门限和状态；FAIL不得被无标注统计覆盖。
- **FR-009**: MUST修正现有批量诊断连续失败段，使其按显式分组断开，不能跨物理组拼接。
- **FR-010**: MUST拒绝把输出写入Git工作树；原图、LabelMe、JSONL、manifest和报告均不提交。
- **FR-011**: MUST保持`algorithms/hole_2/current_capture.py`、配置、Schema和质量门零修改。

## Success criteria

- 合成测试证明同名captureGroup在normal/defective之间不混组。
- 两个显式采集组相邻失败时产生两个失败段，而不是一个跨组失败段。
- 单图真值FAIL仍在报告中明确失败；无标注重复性不能把它变成PASS。
- 静态重复性使用同一captureGroup内有效帧，帧数不足时明确`INCOMPLETE`。
- 服务器外置小样可生成报告，并明确哪些组因帧数/有效数不足而不能评价重复性。
