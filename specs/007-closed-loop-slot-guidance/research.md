# Research: 单真槽闭环旋转引导

## Decision 1: 复用几何检测，只新增引导状态机

**Decision**: 外圆、三暗区、真槽过滤、亚像素槽壁及外圆交点全部复用现有链；引导只消费已验证的槽口中点径向。

**Rationale**: 错误位于状态和下游映射，不在几何检测；重写会破坏已有25/25真槽精修基线。

**Alternatives considered**: 用目栅角直接分类图像；因无法输出闭环修正而拒绝。

## Decision 2: 新single-groove config/result v3，旧v2不静默改语义

**Decision**: 新闭环分支由`single-real-groove-pose-config/3`显式启用，生成`slot-single-real-groove-pose/3`和`slot-pose-result/3`；v1/v2原样保留。

**Rationale**: v2的`valid`与正式机械量绑定，且使用`PASS/FAIL`；原地改义会让旧消费者在无Schema提示时收到不同语义。

**Alternatives considered**: 保持顶层v2仅在diagnostics增字段；因`result.valid=false`仍会阻断闭环而拒绝。

## Decision 3: 图像坐标是数学权威，设备“-Y”是别名

**Decision**: 契约使用图像x右/y下，向下`+Y`射线为0°、顺时针正；设备文档的“-Y下半轴”仅记为physical alias。

**Rationale**: 现有测量与权威例`82.978/22.834/-158.111`只在该约定下一致。

**Alternatives considered**: 将负Y字面解释为图像向上；会立即与三个权威例冲突。

## Decision 4: 死区修正与原始差分字段

**Decision**: 始终计算`correctionRawDeg=wrapTo180(85-current)`；仅当左下且当前角在`[80,90]`时，对外`correctionDeg/imageFrameCorrectionDeg=0`。

**Rationale**: 既保留调试时的微小偏差，又保证闭环不在容差内来回抖动。

**Alternatives considered**: 容差内仍输出到85°的修正；与负责人的死区要求冲突。

## Decision 5: PLC映射是第二级权限门

**Decision**: 图像引导可用与否由检测几何决定；`mechanicalCorrectionDeg/plcCommand`只在现场方向、缩放、地址、字节序和握手契约确认后生成。

**Rationale**: 算法已经知道图像中应转多少，但不能由此推导执行机符号和存储格式。

**Alternatives considered**: PLC未确认时整体fail-closed；这正是需要纠正的旧语义。

## Decision 6: 闭环由外部重拍驱动，算法单帧无状态

**Decision**: 每个`taskId`只消费一帧并输出一个引导状态；上位机日后按“旋转完成→重拍→新taskId”调用，本轮不实现运动控制。

**Rationale**: 无状态算法天然避免失败时复用前帧命令，也便于离线回放。

**Alternatives considered**: 在算法进程内保存闭环状态；会增加过期、并发和恢复风险。
