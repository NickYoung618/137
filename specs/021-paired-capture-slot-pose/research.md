# Research: 双帧配对槽姿态

## Decision 1: 旋转归一化

**Decision**: 图像profile角以+x为0°、y向下所以顺时针增加。两拍间顺时针旋转量记为正R，第二帧候选映射到第一帧零件坐标为`wrap360(theta2 - R)`。

**Rationale**: 同一真槽随零件旋转满足`theta2 ≈ theta1 + R`；相机固定阴影满足`theta2 ≈ theta1`，减R后通常不匹配。

**Alternatives considered**: 用第二帧加R会颠倒正负；用跨帧像素位移会依赖圆心/尺度且难以环绕。

## Decision 2: 未确认参数仍可联调但无权威输出

**Decision**: rotation parameterStatus独立于数值存在性。UNCONFIRMED+空值只输出逐帧候选；UNCONFIRMED+暂定值可输出diagnostic hypotheses，但valid、guidance、mechanical/PLC均为空。

**Rationale**: 允许框架先开发，又不会把测试假设泄漏成现场合同。

## Decision 3: 一对一全候选匹配

**Decision**: 保留每帧最多16个候选，枚举笛卡尔积。以环形角残差为主门，宽度、prominence、deficitArea和可用剖面为独立证据；best-second差距不足即歧义。

**Rationale**: 单帧过早选一个会丢失被遮挡真槽；只选择“第三候选”会在合并/缺失时失效。

## Decision 4: 遮挡与输出时刻

**Decision**: 唯一跨帧匹配还需至少一帧candidate usable。第二帧usable时直接测量；否则从第一帧和已确认旋转传播到第二拍后姿态。

**Rationale**: 双拍保证至少一次无遮挡，但设备在第二次拍摄后已旋转，输出第一拍角会成为过期引导。

## Decision 5: 固定阴影不是固定角屏蔽

**Decision**: 31°/328°只保留在审计诊断中。匹配算法不知道任何固定角窗口，槽位于这些角度附近的合成样例必须通过。

**Rationale**: 真槽可能旋转到固定阴影位置；硬屏蔽直接制造漏检。

## Decision 6: 人工审阅用AUTO_预填而非空白真值模板

**Decision**: 生成raw、019、020三栏材料和AUTO_ shapes；自动圆只展示不要求人工重画。人工只确认真槽边界、两个阴影区域和左右壁是否同源。

**Rationale**: 空白原图无法显示算法实际选边；自动shape必须与human truth命名空间隔离。
