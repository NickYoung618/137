# Spec 021 需求逐条完成审计

**审计基线**: `021-paired-capture-slot-pose@f8f957d9198161eb2a233ef45b4b90bcbdf82a83`

**审计日期**: 2026-08-17

**范围**: Spec 021的FR-001—FR-088、SC-001—SC-036；不使用sealed part-006，不把part-008 145/147的AUTO结果当像素真值。

## 状态定义

- `PROVEN`: 已有契约、确定性测试、真实回放或外置审核证据直接支持。
- `PROVEN_SYNTHETIC`: 代码与数学语义已由合成/单元证明，但真实双拍或像素真值验收尚缺。
- `GUARDRAIL_PROVEN`: 不误升权、不调参、不读封存数据等治理边界已有代码/测试/记录支持。
- `BASELINE_CONTRADICTION_RESOLVED`: 基线规格内有矛盾，本轮只澄清文字，未改运行时语义。
- `MISSING_EXTERNAL_EVIDENCE`: 实现无法代替人工真值、真实双拍数据或现场旋转参数。

## 证据索引

- `P`: `algorithms/slot_pose/paired_capture.py` + `tests/test_paired_capture_slot_pose.py` + paired三份Schema。
- `L`: `algorithms/slot_pose/local_second_wall.py` + `tests/test_local_second_wall.py` + diagnostic v4 Schema。
- `S`: `tests/test_single_real_groove.py`的完整双壁、partial、85±5和PLC阻断回归。
- `R`: `tools/prepare_slot_pose_prefill_review.py`、`tools/build_complete_groove_review_queue.py`及对应测试/Schema。
- `C`: `tools/prepare_fixture_contamination_annotation.py`、`tests/test_fixture_contamination_annotation.py`与`fixture-contamination-review/1` Schema。
- `E`: `evidence.md`的服务器、Mac 140 BMP、part-019人工单壁和最终跨平台门记录。
- `X`: `tools/prepare_clean_groove_pixel_review.py`、`tests/test_clean_groove_pixel_review.py`与`clean-groove-pixel-review/1` Schema。

## Functional Requirements

| ID | 状态 | 直接证据与结论 |
|---|---|---|
| FR-001 | PROVEN | P：manifest/1、sample/pair/capture/SHA/旋转字段和Schema完整。 |
| FR-002 | PROVEN | P：CONFIRMED/UNCONFIRMED两状态及空参数安全分支有测试。 |
| FR-003 | PROVEN | P：运行时检查sample、pairId、路径、SHA和1/2索引；本轮补齐Schema层。 |
| FR-004 | PROVEN | P/E：paired层只消费单帧payload，没有复制拟圆或槽检测。 |
| FR-005 | PROVEN | P：原始、接受/拒绝、refinement、source evidence均保留。 |
| FR-006 | PROVEN | P/S：x-right、y-down、顺时针正和负Y基准均有数值测试。 |
| FR-007 | PROVEN_SYNTHETIC | P：`wrap360(theta2-signedRotation)`正负/环绕达1e-9数值证据；缺真实已知旋转对。 |
| FR-008 | PROVEN_SYNTHETIC | P：全候选假设、差异、best/second和failedChecks已测；缺真实双拍裁决。 |
| FR-009 | PROVEN | P/L：31°/328°合成回归能枚举真槽，无ignore mask。 |
| FR-010 | PROVEN_SYNTHETIC | P：唯一匹配+至少一帧usable才valid；缺真实双拍验收。 |
| FR-011 | PROVEN | P：缺帧、未确认、多解、超上限、残差和身份错配均fail-closed。 |
| FR-012 | PROVEN | P：UNCONFIRMED+临时数值只产生DIAGNOSTIC_ONLY，角/PLC为null。 |
| FR-013 | PROVEN_SYNTHETIC | P：current image与part-relative已分字段并测试；缺真实双拍数值对照。 |
| FR-014 | PROVEN | P/S：85°、5°、80/90闭区间、wrapTo180和方向均有边界测试。 |
| FR-015 | PROVEN | P/S：image correction与PLC分离，PLC始终NOT_AUTHORIZED/null。 |
| FR-016 | PROVEN | P：严格配置、未知字段拒绝、enabled=false和上限门完整。 |
| FR-017 | PROVEN | P：三份Schema+契约测试；本轮补齐索引、路径和CONFIRMED条件。 |
| FR-018 | PROVEN | P：正/负、环绕、31/328、单帧usable、歧义、错配和旋转误差均覆盖。 |
| FR-019 | GUARDRAIL_PROVEN | E/R：封存sample/SHA有拒绝测试，140盘点不含part-006。 |
| FR-020 | GUARDRAIL_PROVEN | P/L/E：新功能默认不执行，legacy全量门通过。 |
| FR-021 | PROVEN | R/E：374/369的raw、simplified、联系表、AUTO JSON与review index已外置生成。 |
| FR-022 | PROVEN | R：白名单shape和禁止圆/框/raw ray/伪真值有自动测试。 |
| FR-023 | PROVEN | R：原图/结果SHA不一致时写出前拒绝，路径/媒体污染门通过。 |
| FR-024 | GUARDRAIL_PROVEN | E：292明确跳过，优先374/369。 |
| FR-025 | GUARDRAIL_PROVEN | S/E：132112_4只用作development reference，运行时无人工真值依赖。 |
| FR-026 | PROVEN | R：墙/端点稳定颜色及橙色角度区间测试通过。 |
| FR-027 | PROVEN | R：标题、简明图例和非valid声明已固化。 |
| FR-028 | PROVEN | R：AUTO_、human_verified=false和拒绝覆盖人工shape已测。 |
| FR-029 | PROVEN | R：只用selectedCandidateIds，NOT_MATCHED/PAIR_INCOMPLETE不nearest补位。 |
| FR-030 | PROVEN | R：start/center/end括号+三刻线，无实心区域。 |
| FR-031 | PROVEN | R：三项边界声明和无区间时降级方向证据已测。 |
| FR-032 | PROVEN | R：interval linestrip与flags完整，不冒充fixture确认区。 |
| FR-033 | PROVEN | L/E：374/369混合边负例被保护，运行时无文件名/角度/坐标硬编码。 |
| FR-034 | PROVEN | L：配置/2严格且默认关闭。 |
| FR-035 | PROVEN | L：start/end均生成inward/outward域，不再是硬边界。 |
| FR-036 | PROVEN_SYNTHETIC | L：几何、端点、连通、槽肩、同源硬门已合成验证；真图像素真值尚缺。 |
| FR-037 | PROVEN | L/S：唯一实验解也不能提升顶层姿态。 |
| FR-038 | BASELINE_CONTRADICTION_RESOLVED | 基线文字与FR-062—065冲突；现澄清为0墙=NOT_FOUND、有墙无完整对=PARTIAL、多完整解=AMBIGUOUS。 |
| FR-039 | PROVEN | L：31°/328°无屏蔽合成测试。 |
| FR-040 | PROVEN | L：失败库、failureStage和PARTIAL区分完整。 |
| FR-041 | PROVEN | L：layer/hardGate可审计，score不能越过硬门。 |
| FR-042 | PROVEN_SYNTHETIC | L：任意旋转、环绕、曝光/模糊/不对称/部分重叠已合成量化；真实精度不可推广。 |
| FR-043 | PROVEN | L：每seed的角、窗口、点、直线、线段和拒绝阶段均输出。 |
| FR-044 | PROVEN | L：cluster member/suppressed/代表/规则可对账。 |
| FR-045 | PROVEN | L：anchor来源、原始端点、极性和coarse来源已输出。 |
| FR-046 | PROVEN | L：pre/post merge分开，三类search outcome已覆盖。 |
| FR-047 | PROVEN | L：所有domain/seed/candidate上限严格校验且受槽宽限制。 |
| FR-048 | PROVEN_SYNTHETIC | L：墙从梯度+直线+交点独立生成；真图完整双壁尚待确认。 |
| FR-049 | PROVEN | L：canonical pair与端点顺序无关。 |
| FR-050 | PROVEN | L：0.5°物理墙merge守恒和不合并不同墙有测试。 |
| FR-051 | PROVEN | L：domain/seed/wall cluster/canonical pair/failedChecks全链可审计。 |
| FR-052 | PROVEN | L：fixture证据是软证据，31/328不否决候选。 |
| FR-053 | PROVEN | E：140张分组回放及上游错误分布已记录，0/140 valid未被包装成准确率。 |
| FR-054 | PROVEN | R/E：374/369已生成不权威简化图，人工反馈未写成自动真值。 |
| FR-055 | GUARDRAIL_PROVEN | L/E：0.12、0.5°、默认关闭、顶层失败和PLC阻断均不变。 |
| FR-056 | PROVEN | E：原人工JSON、派生副本和压缩包SHA外置复核，原件未覆盖。 |
| FR-057 | PROVEN | E：误命名shape已安全解释为“可见真壁”，opposite_wall_truth=false。 |
| FR-058 | PROVEN | E/L：285.953°仅是人工确认可见真壁，309.48°阴影边不得配对。 |
| FR-059 | PROVEN | L/S/E：单壁、遮挡、可观测性未知均valid=false，不合成隐藏壁。 |
| FR-060 | PROVEN | L：双向搜索只枚举可见像素证据，搜不到不被解释为人工必须猜线。 |
| FR-061 | PROVEN_SYNTHETIC | P/L：提升需至少一帧完整同源双壁已在契约中；真实双拍尚缺。 |
| FR-062 | PROVEN | L：diagnostic/4已版本化PARTIALLY_OBSERVED。 |
| FR-063 | PROVEN | L/S：partial时authoritative=false、promotion=false、candidate/angle/PLC全空。 |
| FR-064 | PROVEN | L：cluster ID、evidence count、complete=false、runtime human=false、opposite=UNCONFIRMED已固化。 |
| FR-065 | PROVEN | L/S/E：Mac/Server回放的33个partial均保持顶层GROOVE_SOURCE_INCONSISTENT/invalid。 |
| FR-066 | PROVEN_SYNTHETIC | S：完整双壁合成链保持DETECTED与85±5引导；缺真实完整槽真值。 |
| FR-067 | PROVEN | L/S：`reuses_rejected_initial_pair`和source hard gate阻断374结构。 |
| FR-068 | PROVEN | R：多manifest/JSONL、sample汇总、路径安全和只读CLI已测。 |
| FR-069 | PROVEN | R/E：先sample证据、后SHA稳定抽帧，禁止角度/置信/门限择样。 |
| FR-070 | PROVEN | R/E：队列JSON/CSV/manifest外置，A2相对路径、SHA和三个false声明完整。 |
| FR-071 | PROVEN | C/E：145/147均保留最终A：真槽、完整可见、槽肩端点及干净AUTO槽壁均确认；fixture只对应非槽候选标记且区域不完整。 |
| FR-072 | PROVEN | C/E：干净槽壁语义、非槽阴影候选、不完整fixture区域和pixel truth分开表达；AUTO坐标不升权。 |
| FR-073 | PROVEN | C：旧`fixture-contamination-review/1`和派生LabelMe已标为DORMANT/INAPPLICABLE，不再要求或导入墙污染子段。 |
| FR-074 | PROVEN | C：兼容CLI在读输入/建目录/写文件前稳定拒绝；历史文件保留不覆盖。 |
| FR-075 | PROVEN_SPEC / MISSING_EXTERNAL_EVIDENCE | 最小像素复核已定义为每墙至少3个独立支持点+两端点；坐标尚未画制。 |
| FR-076 | GUARDRAIL_PROVEN + MISSING_EXTERNAL_EVIDENCE | 墙/端点及独立外圆真值未到位，因此pixel truth、准确率和调参权限保持false。 |
| FR-077 | PROVEN | C/E：非槽fixture标记不完整被保留为独立缺口，不否定干净槽壁也不用于调参。 |
| FR-078 | GUARDRAIL_PROVEN | C：语义、历史产物和未来像素复核均禁止runtime/PLC/tuning，未改生产检测。 |
| FR-079 | PROVEN | X：`clean-groove-pixel-review/1`、prepare/validate CLI和Git外路径门已实现。 |
| FR-080 | PROVEN | X：AUTO文件只哈希不解析；生成LabelMe恒为`shapes=[]`、`imageData=null`。 |
| FR-081 | PROVEN_IMPLEMENTATION / MISSING_EXTERNAL_EVIDENCE | X：每墙>=3个独立point强制校验；145/147实际人工点尚待绘制。 |
| FR-082 | PROVEN_IMPLEMENTATION / MISSING_EXTERNAL_EVIDENCE | X：左右端点各1个point强制校验；实际坐标尚待绘制。 |
| FR-083 | PROVEN_IMPLEMENTATION / MISSING_EXTERNAL_EVIDENCE | X：可选>=8点圆弧或独立圆心与墙/端点状态分开；实际外圆参考尚缺。 |
| FR-084 | PROVEN | X：AUTO/旧污染label、坐标/类型/边界/复制与人工flags失败分支均fail-closed且不写报告。 |
| FR-085 | PROVEN | X：墙、端点、外圆、完成与姿态角ready五状态分字段，全部权限恒false。 |
| FR-086 | PROVEN | X：显式身份、SHA、truthPolicy、路径、输出存在及sealed part-006门均有测试。 |
| FR-087 | PROVEN | C/X：旧CLI仍DORMANT；新工具无fixture overlap标签或边界请求。 |
| FR-088 | GUARDRAIL_PROVEN | X/E：仅离线工具/契约/文档；算法、阈值、main和PLC未改。 |

## Success Criteria

| ID | 状态 | 直接证据与结论 |
|---|---|---|
| SC-001 | PROVEN | P：运行时与Schema现均拒绝结构/参数/路径/索引错误，并按SHA对账。 |
| SC-002 | PROVEN_SYNTHETIC | P：正负/环绕精确度与固定阴影不匹配已测；缺真实对。 |
| SC-003 | PROVEN | P/L：31°/328°测试100%通过。 |
| SC-004 | PROVEN | P/L/S：指定失败分支均valid=false且无PLC。 |
| SC-005 | PROVEN_SYNTHETIC | P/S：单帧usable、顺/逆、80/90已测；缺真实对。 |
| SC-006 | PROVEN | E：默认关闭和服务器/Mac全量无回退。 |
| SC-007 | PROVEN | R/E：374/369完整审阅包与禁止元素测试通过。 |
| SC-008 | PROVEN | E：完成审计提交的服务器425项与Mac 397项均通过；Mac 16项平台skip，39份Schema、CLI和污染门通过。 |
| SC-009 | GUARDRAIL_PROVEN + MISSING_EXTERNAL_EVIDENCE | 没有真实双拍/确认参数，所以正确结论就是不宣称准确率、不合main。 |
| SC-010 | PROVEN | R：NOT_MATCHED/PAIR_INCOMPLETE与flags合成测试通过。 |
| SC-011 | PROVEN_SYNTHETIC | L：方形槽、fixture跨源、多解、缺边、31/328已覆盖。 |
| SC-012 | PROVEN | L/S/E：开关不改顶层失败与PLC。 |
| SC-013 | PROVEN_SYNTHETIC + MISSING_EXTERNAL_EVIDENCE | 合成端点<0.15°、中点<0.10°测试通过；不能代表A2真实像素精度。 |
| SC-014 | PROVEN | L/R：seed/cluster/pre-post守恒与脱敏trace已测。 |
| SC-015 | PROVEN_SYNTHETIC | L：start/end外侧、环绕、fixture内侧、0/多解已覆盖。 |
| SC-016 | PROVEN | L：墙cluster归属守恒、canonical ID及反转不变已测。 |
| SC-017 | PROVEN | E：140/140 diagnostic/3可解析，分组失败和不提升已记录。 |
| SC-018 | PROVEN | L/E：上限门测试、默认关闭、legacy<8s及paired matcher P95 2.17ms<20ms。 |
| SC-019 | PROVEN | E：原/派生SHA与两点保留已外置复核。 |
| SC-020 | PROVEN | L/S/E：人工真壁+阴影边不生成中点/姿态/PLC，0.12不变。 |
| SC-021 | PROVEN | L/S：单墙/同源失败为PARTIAL，0墙NOT_FOUND，多完整解AMBIGUOUS。 |
| SC-022 | PROVEN | L/S/E：374结构无experimentalCandidate/端点/中点/引导。 |
| SC-023 | PROVEN_SYNTHETIC | S：完整双壁运行时语义无回退；真实完整双壁尚待人工裁决。 |
| SC-024 | PROVEN | R/E：140张按sample对账，排除part-006/019，Mac/服务器均选147、145。 |
| SC-025 | PROVEN | E：6f12585的服务器/Mac全量、39份Schema及CLI门通过，默认、0.12、0.5°、main和PLC不变。 |
| SC-026 | PROVEN | C/E：最终A语义与auto/pixel truth、accuracy、tuning=false已固化。 |
| SC-027 | PROVEN | C：旧CLI函数与命令行测试100%在写出前返回DORMANT/INAPPLICABLE，输出目录不存在。 |
| SC-028 | PROVEN | C/E：两份历史LabelMe SHA保留，已标为dormant/inapplicable，不要求删除或补画。 |
| SC-029 | PROVEN_SPEC / MISSING_EXTERNAL_EVIDENCE | 像素复核定义不含fixture overlap，只含每墙至少3点+两端点；待人工实际绘制。 |
| SC-030 | PROVEN | C/E：更正后服务器428项与Mac 400项全量门、40份Schema、dormant CLI零输出拒绝均通过；算法、140图结果、门限、main和PLC未改。 |
| SC-031 | PROVEN | X：测试以不可解析AUTO文件验证只哈希；两张任务均零shape/零imageData。 |
| SC-032 | PROVEN | X：3+3、端点、重复/类型/非有限/越界/AUTO/旧污染/复制失败全覆盖。 |
| SC-033 | PROVEN_IMPLEMENTATION / MISSING_EXTERNAL_EVIDENCE | X：无外圆与arc/center三分支通过；真实145/147标注尚待返回。 |
| SC-034 | PROVEN | X：身份、SHA、策略、Git内/已存在输出均写前拒绝，无媒体进Git。 |
| SC-035 | PROVEN | C/X：旧停用测试与新工具禁用fixture overlap测试同时通过。 |
| SC-036 | PROVEN_SERVER / PENDING_MAC_GATE | X/E：服务器436项全量、41份Schema和污染门通过；待Mac独立门，期间不合main。 |

## 被证据否定或纠正的旧理解

1. **FR-038基线文字矛盾**: 有单墙证据但无完整对不能称为“完全没找到第二壁”；应是非权威`PARTIALLY_OBSERVED`。本轮仅澄清规格，当前代码原本已符合这一安全语义。
2. **part-019“恢复了完整槽”已被否定**: 285.953°是人工确认的一条可见真槽壁，309.48°是fixture shadow edge；稳定混合配对不是稳定正确。
3. **“单帧必须恢复另一壁”已被纠正**: 如果相对壁被遮挡，算法不能从不可见像素补造；正确结果是fail-closed/partial，双拍需至少一帧完整可见。
4. **真实完整姿态链尚未证明**: 当前140张的实验结果是0/140顶层valid；它证明fail-closed和诊断可复现，不证明真实槽角精度或检出率。
5. **145/147槽壁污染推论已被否定**: 最终A确认两条AUTO槽壁本身正确干净；阴影只对应非槽候选标记且标记不完整。旧污染请求已停用。

## 当前人工语义后可安全完成的工作

- 已完成FR-038语义澄清，无运行时变更。
- 已完成paired manifest Schema与运行时的跨平台先验一致性。
- 已完成本逐条审计；它明确区分“实现完成”和“真实验收完成”。
- 已原样记录145/147的身份、可见性、槽肩端点和干净槽壁A语义，并分开非槽fixture标记不完整。
- 已停用“槽壁fixture污染子段”请求，保留历史产物但不继续补画。
- **在独立墙支持点、槽口端点与外圆真值返回前，没有对齐的核心算法或门限修改可安全继续**。

## 当前缺失的验收证据

### A. part-008 145/147已获得的最小人工裁决

两张都已得到下列回答：

1. 两条AUTO墙是否确实属于**同一个真实方形槽口**？
2. 该槽口是否**两侧完整可见、未遮挡**？
3. 两个AUTO槽口端点是否位于**真实外圆槽肩交点**？
4. 两条AUTO槽壁本身正确干净：**YES**；只有其他非槽候选标记落在fixture shadow上，而且阴影区域标记不完整。

这四问确认槽身份、槽壁干净性和端点物理语义，但仍不是亚像素坐标真值。

### B. 下一个最小人工动作：干净槽壁像素复核

旧污染派生LabelMe不再补画。对每条干净槽壁独立点选至少3个沿可见墙分散的支持点，再独立标左/右槽口端点。坐标不得从AUTO线复制，不要求fixture shadow边界。

### C. 像素级姿态精度验收

若145或147中至少一张被确认为完整可见，还需对同一图像SHA保存Git外的LabelMe真值：左/右真槽壁、两个槽口端点（或完整开放槽边界），以及能独立复核圆心的外圆可见弧/圆心真值。算法自己的拟合圆不能同时作为自己的准确度真值。

### D. 双拍验收

至少需一个同物理件真实pair，包含capture 1/2的原图SHA、CONFIRMED nominalRotationDeg、rotationDirection、rotationToleranceDeg，并人工确认至少一拍完整无遮挡。要声称生产性能，还需多物理件、多角度的独立真值集与端到端耗时/有效率/失败率报告。
