# Research: 单人工样板驱动的无真值诊断

## Decision 1: 人工样板只对自身提供误差

**Decision**: 仅保留参考BMP的人工/自动圆和槽角差；其他图只有观测值。

**Rationale**: 不同图可能是不同姿态，共享一个角会制造假真值。

**Alternatives considered**: 将参考角应用到全批；因不能证明物理姿态相同而拒绝。

## Decision 2: 自动LabelMe与人工truth物理分离

**Decision**: 使用独立外置目录和`AUTO_`标签，所有truth相关旗标为false。

**Rationale**: 既方便在LabelMe看算法结果，又避免将预测当成人工答案。

**Alternatives considered**: 预填人工模板；会破坏独立标注和后续真值审阅。

## Decision 3: 观测差使用环形数学但不叫误差

**Decision**: 字段固定为`observedCircularDeltaToReferenceDeg`，范围`[-180,180)`。

**Rationale**: 角度必须处理±180环绕，同时避免accuracy语义越界。

**Alternatives considered**: 原始角直减或命名为error；前者跨边界错误，后者语义错误。
