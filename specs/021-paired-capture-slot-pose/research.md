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

## Decision 6: 人工审阅用精简AUTO_预填而非空白真值模板

**Decision**: 生成RAW/SIMPLIFIED两栏材料和精简AUTO_ shapes。简化图只显示019最终左右壁/端点与020
观测暗区；不画圆、定位框、非最终raw射线或真值框。优先使用pairEvidence.selectedCandidateIds，但即使模板匹配也只画
raw start/center/end对应的圆周角度括号与三刻线，声明fixture身份未确认、像素边界未知。NOT_MATCHED不得nearest补成A/B；
无区间时才画短方向箭头。

**Rationale**: 空白原图无法显示算法实际选边，完整调试overlay又会淹没待确认对象；自动shape必须与
human truth命名空间隔离，拟合圆可在算法诊断中保留但不进入本轮人工复核画面。

## Decision 7: 粗暗区是定位证据而不是搜索边界

**Decision**: 原start/end只作为待验证anchor和搜索域原点。start向更小角度、end向更大角度的outward域与各自inward域同时生效，全部wrap360。扩展上限不得超过物理槽宽上限，总seed和接受墙数有硬上限。

**Rationale**: 140张diagnostic/2 trace确认part-019的真实另一壁在merge前已missing；只在286.125°‒309.125°内部扫描必然复现两个错误端点。向外扩展修正生成域，物理宽度上限防止无界扩展到远处fixture。

**Alternatives considered**: 放宽0.12会直接接受已知混合边；仅增大0.5° merge或调小merge不会生成一个原本不存在的墙cluster；两者均拒绝。

## Decision 8: 先独立物理墙、后无序墙对

**Decision**: 每个domain/seed/polarity独立运行亚像素梯度、共识直线和外圆交点；所有接受拟合再按极性与相近角度聚成physical wall。墙对在cluster层一次枚举，canonical ID由排序后的两个cluster ID构成，不再生成A锚B/B锚A顺序重复。

**Rationale**: anchor是来源证据而不是墙真值。先墙后对可以区分“未生成”、“被聚类”和“配对后硬门拒绝”，并保证顺序反转不改变假设数。

**Alternatives considered**: 继续把原start/end直接放入墙对会保留错误先验；先按anchor生成有序假设再merge会隐藏候选生成问题。
