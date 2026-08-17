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

## Decision 12: 历史误解，已被Decision 13取代

**Superseded decision**: 先前将“某些标记落在fixture shadow”解释为“AUTO槽壁局部受污染”，并生成墙污染子段请求。最终人工选择A证明该推论不成立；本决策只作历史记录，不得继续执行。

## Decision 13: 确认干净槽壁语义，停用污染请求并改为独立像素支持点复核

**Decision**: 145/147的最终语义是两条AUTO槽壁正确干净；fixture shadow只对应其他非槽候选标记，且阴影区域未完整标出。旧污染请求与派生LabelMe保留为DORMANT/INAPPLICABLE历史证据，不补画、不导入。下一个最小像素复核是人工独立标出每墙至少3个分散支持点和两槽口端点；不从AUTO坐标生成HUMAN坐标，不要求fixture边界。

**Rationale**: A已解决槽壁物理身份与污染归属，但语义判断无法量化亚像素墙位置、端点误差或圆心误差。分散支持点是独立检查两条直壁像素位置的最小证据；两端点单独标注用于检查槽口中点。最终姿态角精度还需独立外圆可见弧或圆心真值。

**Alternatives considered**: 继续画槽壁污染子段与A冲突；把AUTO线直接当像素真值会自证；立即补全两处fixture shadow边界不是验证干净槽壁的最小必要证据。三者均拒绝。

## Decision 14: 空白独立LabelMe任务与分阶段完成门

**Decision**: 145/147像素复核从`shapes=[]`的原图任务开始，AUTO LabelMe只核SHA、不解析或复制shape。人工以point分别标每墙至少3个分散支持点和左右端点。外圆参考允许同图独立可见弧（至少8点linestrip）或独立圆心point，并与墙/端点完成状态分开。

**Rationale**: 即使AUTO线在语义上正确，显示或复制其点列也会让人工结果失去独立性。3个点是验证一条直壁的最小非退化支撑；两个端点直接决定槽口中点。外圆中心误差会传入最终角度，因此墙端点复核完成不能自动代表角度精度就绪。

**Alternatives considered**: 把AUTO shape留在同一LabelMe会造成锚定偏差；用两点定义墙无法独立检查中间直线支撑；强迫本轮立即标外圆会把最小槽壁任务与最终角精度门混为一体。三者均拒绝。

## Decision 15: 槽壁/端点残差与最终姿态角精度分开

**Decision**: 145/147的3+3墙点与2端点只用于离线评估AUTO墙线、槽肩交点、槽口中点和槽宽。没有独立外圆弧或圆心时，方向残差必须让HUMAN/AUTO中点共用同一个runtime物理圆心，并明确称为条件方向残差。

**Rationale**: 槽姿态方向同时依赖槽口中点和圆心。共用runtime圆心可以隔离槽口定位对角度的贡献，但不能测量圆心偏差，也不能代表完整姿态角精度。

**Alternatives considered**: 把runtime圆心当人工真值会自证外圆算法；仅比较两端点欧氏距离会隐藏墙拟合与槽宽误差；因缺圆真值完全不做诊断又浪费已完成的独立槽像素证据。三者均拒绝。

## Decision 16: 不放宽contrast门，增加不可升权的多证据候选

**Decision**: 保留现有`edge_contrast_asymmetry <= 0.12`生产硬门不变。新增默认关闭的development-only候选：只有原结果恰好只失败contrast、其余原检查均通过，并且独立端点结构差异门通过时，才输出`CANDIDATE_SUPPORTED`诊断；原结果继续失败且不得输出姿态。

**Rationale**: 145/147人工确认的真实双壁contrast normalized difference约0.173–0.193，反而高于part-019已知混合边约0.127–0.138。单纯放宽contrast会先恢复已知错误配对。两组现有证据中，端点结构差异的范围分离（145/147所在part-008约0.019–0.023，part-019约0.076–0.081），可用于验证一种更合理的多证据候选，但样品数太少，不能生产启用。

**Alternatives considered**: 把contrast阈值放宽到0.20会放过part-019；用part/sample ID或固定角规则会把真值泄漏到运行时；直接用HUMAN坐标纠正AUTO会违反独立验证。均拒绝。

## Decision 17: runtime按image SHA关联而不是近似AUTO审阅产物

**Decision**: 残差CLI按正式validation中的image SHA与canonical runtime JSONL唯一关联，并验证HUMAN LabelMe SHA。AUTO审阅LabelMe只保留来源审计，不在源文件SHA不一致时用basename近似替代。

**Rationale**: 服务器已有的历史AUTO审阅副本与Mac任务清单中的AUTO SHA不同；按文件名近似匹配会破坏溯源。runtime JSONL包含同图物理圆、墙线、支持点和交点，并可用图像SHA精确绑定。

**Alternatives considered**: 使用同名历史AUTO文件会混淆版本；要求上传原图或复制9.5MB LabelMe进Git没有必要；重跑图像会引入与已冻结结果不同的新状态。均拒绝。
