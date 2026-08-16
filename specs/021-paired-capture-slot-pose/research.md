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

**Rationale**: 140张diagnostic/2 trace确认原搜索在merge前没有生成额外墙cluster；只在286.125°‒309.125°内部扫描会复现两个错误端点。后续374人工线证明285.953°既有cluster就是一条可见真槽壁，但没有证明相对侧壁在该帧可见。因此向外扩展只能修正“可见证据搜索域”缺陷，不能被解释为必须恢复一条可能被遮挡的真实壁。

**Alternatives considered**: 放宽0.12会直接接受已知混合边；仅增大0.5° merge或调小merge不会生成一个原本不存在的墙cluster；两者均拒绝。

## Decision 8: 先独立物理墙、后无序墙对

**Decision**: 每个domain/seed/polarity独立运行亚像素梯度、共识直线和外圆交点；所有接受拟合再按极性与相近角度聚成physical wall。墙对在cluster层一次枚举，canonical ID由排序后的两个cluster ID构成，不再生成A锚B/B锚A顺序重复。

**Rationale**: anchor是来源证据而不是墙真值。先墙后对可以区分“未生成”、“被聚类”和“配对后硬门拒绝”，并保证顺序反转不改变假设数。

**Alternatives considered**: 继续把原start/end直接放入墙对会保留错误先验；先按anchor生成有序假设再merge会隐藏候选生成问题。

## Decision 9: 先判可观测性，不从单帧补造被遮挡侧壁

**Decision**: 将Mac人工shape的几何语义记录为“已确认可见真实槽壁”，而不是按误命名label解释为“缺失侧壁”。原文件与SHA保留，只允许派生审核副本规范语义。单帧只有一条可见真壁时继续fail-closed；局部Cartesian搜索只枚举可见墙，不能推断隐藏墙或完整槽中点。双拍必须至少提供一张完整无遮挡开口。

**Rationale**: 人工两点线与AUTO 285.953°墙cluster高度重合；309.48°已被确认为fixture shadow edge。把该线当另一壁会制造错误监督，把阴影边配入真槽；要求人工猜不可见边同样不可复核。

**Alternatives considered**: 按label字面训练第二壁会污染真值；用槽宽先验镜像生成第二壁会给出不可观测的伪测量；放宽0.12会重新接受已知混合边。三者均拒绝。未来可升版增加`PARTIALLY_OBSERVED`诊断状态，但它不得提升valid或引导。

## Decision 10: PARTIALLY_OBSERVED只描述证据充分性

**Decision**: 局部诊断升至v4。当至少一个墙状cluster存在，但只有单墙或所有墙对都因已拒绝初始对/同源性失败而不能形成完整开口时，状态为`PARTIALLY_OBSERVED`。输出全部cluster但不指定哪条是真槽壁，`experimentalCandidate`为空，外层仍`GROOVE_SOURCE_INCONSISTENT`。

**Rationale**: 374人工审核能确认某一既有cluster是真壁，但生产运行时不得读取该标签。把“运行时看见墙状边”与“人工确认物理身份”分开，既能表达遮挡，又不会把阴影边包装成真实槽。

**Alternatives considered**: 继续统一为`SOURCE_INCONSISTENT`无法区分完全缺失与部分可见；运行时绑定374坐标会泄漏真值并过拟合；把partial设为valid违反fail-closed。均拒绝。

## Decision 11: 完整槽队列按sample筛选、按SHA选帧

**Decision**: 只读汇总140张冻结manifest/JSONL，先找至少两帧具有双壁refinement或physical-wall-cluster证据的sample；显式排除已有人工partial/mixed判定的sample；候选sample内用`sha256(sampleId|imageSha)`固定选择两帧。输出只含相对路径、SHA、阶段证据和人工问题。

**Rationale**: 算法证据可用于决定“人工先看哪里”，但不能成为真值或用角度表现挑样。按sample防止把同一零件拆散，按身份散列避免肉眼/结果择优。

**Alternatives considered**: 选最接近门限或最稳定帧会引入调参偏差；随机无种子不可复现；把part-019当正向候选与已知partial证据冲突。均拒绝。
