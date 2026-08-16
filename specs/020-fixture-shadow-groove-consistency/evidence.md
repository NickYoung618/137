# Evidence: A2固定阴影与真槽同源性

## 代码与分支基线

- 功能分支：020-fixture-shadow-groove-consistency。
- 起点：84d7068198d2462b6ae57e6c17b82c3873cc6619（未合入main的019功能分支）。
- main与origin/main在开发开始时均为04d179628a6f3f7f2a30d2a4884ce5ef98abfffa。
- merge-base为04d179628a6f3f7f2a30d2a4884ce5ef98abfffa；没有reset、rewrite、main合并或PLC/上位机修改。
- 020配置字段默认关闭；019默认/实验行为由既有配置决定，020不把实验开关改成默认。

## 历史JSON证据复算

审计严格先按封存sampleId和SHA排除part-006，再打开历史results；sealedRecordsParsed=0，accuracyEvaluated=false。
外置audit.json的SHA-256为548c931faafca5443e603d26e269577cfd70d279c7eba3ea403f567086bd80cb。

- normal目标记录480，唯一SHA匹配480。
- raw候选数分布：0个67、1个38、2个60、3个312、4个3。
- 严格三候选定义命中302帧：一处25至40度、一处315至340度、其余恰好一处。
- 阴影A中心角中位31.394264867度，范围30.597079401至31.837008828度；半宽中位10.875度；
  prominence中位103.328528；deficitArea中位311.221162、最大1105.337728。
- 阴影B中心角中位327.745817597度，范围326.373776343至328.188463679度；半宽中位11.125度；
  prominence中位98.865673；deficitArea中位277.710930、最大1074.727425。
- 第三候选中心跨1.762705至357.188056度；prominence中位147.301700；deficitArea中位1427.879399，
  范围1176.796269至2338.501606。该分离只证明历史候选统计，不证明物理类别真值。
- “365/413帧宽松成对”缺少可执行的宽松角窗/匹配定义，审计仅记录definition_missing，不能独立复现为规范结论。
- 约31度和328度在所有实现与测试中只作nuisance prior，不作ignore mask；rawCandidateIds完整保留，
  candidateSuppressionApplied恒为false。

## 标注队列治理

外置annotation-queue.csv的SHA-256为6aa64f13e983657055030614746b5334f33988eced5b64d5be1b2484d9f006b4，
按sampleId与源图SHA确定性选择part-015、part-019、part-021各2帧。每帧要求至少保留：
outer_circle_visible_arc、real_groove_boundary、groove_sidewalls、groove_mouth_endpoints、
fixture_shadow_a_region、fixture_shadow_b_region。humanVerified初值为false，队列不预填真值。

## 服务器25张JPEG诊断

输入为仓库外25张5472x3648 JPEG诊断副本，不是原始BMP，也没有逐图物理真值。019同一配置在本次回放中
自动valid为25/25；启用020实验门后自动valid为2/25，另外23张以GROOVE_SOURCE_INCONSISTENT安全失败。
23张中edge_contrast_asymmetry出现23次，edge_gradient_asymmetry出现20次；固定阴影成对状态为complete 2、
incomplete 20、inconsistent 3。该结果说明门控生效但明显偏保守，不能称为准确率提升、7组修复或生产可用。
不得根据这25张无真值结果放宽阈值；2张自动valid也仍需人工确认两侧壁确属同一真实槽。

最终实现回放仍为2/25自动valid、23/25同源失败，固定阴影配对状态和失败项分布不变；最终结果SHA-256为
0156cb59b0295bf5f0d3fb3d822e62b83abbe007abf2b22bf51c27a778ac9d66。反向性能回放产物SHA：

- 019结果：4b792c7f9a2828401b7db90cc8e394da56bb3f5eb9b39b066bb971458cbd4fb0。
- 020结果：ddec89ed31e86206dc69a74e9072c8d42645636f0f2772d355d239466ed94694。

## Mac 140张原始BMP三折配对证据

以下为2026-08-16由Mac执行端回传的现场证据；服务器未同步原始BMP或逐条结果，因此本节记录为
USER_REPORTED_MAC_VALIDATION，不冒充服务器独立复算。Mac在独立020-mac-validation分支检出
db2f7a0f2fe5d31f9c85a4a0e06c55e5a8e31190，未合并main；使用robustness-019-server的三折
validation manifests回放140张原始BMP，sealed part-006不在输入中。外置产物标识为Mac 009工作区下的
fixture-shadow-020目录，绝对路径不写入Git。

- 019实验配置SHA-256前缀e96adf07，020实验配置SHA-256前缀04cc44cc；当前仅收到前缀，未伪造完整哈希。
- 019自动valid为33/140：part-019为20张，part-008为13张；其余107张保持既有fail-closed。
- 020自动valid为0/140：把上述33张全部拒绝为GROOVE_SOURCE_INCONSISTENT，统一失败硬门为
  source_consistency:edge_contrast_asymmetry。
- part-019的contrastNormalizedDifference约0.1272至0.1380。该组此前已由人工确认存在“真槽一侧+固定
  阴影一侧”的混合配对，因此20/20被阻断是明确false-positive回归证据，但仍不是整体准确率。
- part-008的13张contrastNormalizedDifference约0.1731至0.1927，也被020拒绝；该组没有人工真值，当前
  既不能称为误杀，也不能称为正确拒绝，更不能用它调整0.12门限。
- 本次结果证明当前020硬门足以拦截已知part-019混合配对，同时也证明它对无标签样本极保守。自动valid从
  33降为0不等于准确率提高；生产默认继续关闭，main继续不合并。

发布裁决维持不变：先完成part-015/019/021共6帧LabelMe，明确real_groove_boundary、两处
fixture_shadow区域、两侧壁物理来源和槽口端点，再在标签上裁决门限与重叠分解。禁止依据本批无真值拒绝率
继续调参。

## 性能与资源

共享服务器为2 CPU、约7.5 GiB，测试期间其他项目dotnet任务令load average从约1.4升到12.3，端到端成对墙钟
不具备稳定的同机独占条件。首次019/020墙钟分别1:16.05/2:28.91；反向运行020/019分别1:02.67/2:20.18，
运行顺序完全反转结论，证明共享负载污染。低负载020内部elapsed P50/P95/max为2249.02/2355.80/2386.42 ms；
峰值RSS为1191372 KiB，低于1.5 GiB门。纯新增fixture匹配加同源评估1000次合计466.312 ms，约0.47 ms/次。

因此内存门通过、算法新增计算量有微基准证据，但SC-012的端到端“相对P95新增不超过0.8秒”在非独占服务器上
仍未得到可信成对证明，状态为BLOCKED_PERFORMANCE_ENVIRONMENT。Mac原始BMP三折回放应记录同机相邻运行、
CPU/内存和顺序反转结果后再裁决；不得以当前被污染墙钟宣称通过或失败。

## 测试与Schema

- 聚焦测试：71 tests，18.782秒，全部通过。
- 全量测试：365 tests，110.142秒，全部通过。
- 020运行时/合成聚焦：63 tests，13.281秒，全部通过。
- Slot pose契约聚焦：23 tests，1.722秒，全部通过。
- 仓库98个JSON均可解析；两个slot pose Schema自校验通过；外置020配置通过配置Schema；25条真实回放
  结果全部通过结果Schema。
- 验证同时修复一个既有契约缺口：运行时已有slot-pose-result/3，但机器Schema此前只描述v2；现在Schema
  同时严格描述v2与既有v3字段，不改变运行时算法或默认行为。

## 残余BLOCKED

1. part-019至少2帧必须人工标注真实槽边界和两处固定阴影；在此之前只有已知混合配对反例，没有完整真值。
2. part-015/021槽阴影重叠分解必须在各2帧标签上验证；当前模板没有人工确认的局部剖面，因此分解默认关闭。
3. 服务器仍没有140张Mac原始BMP；Mac三折配对已经执行，但服务器只有用户回传统计，不能独立复算逐条结果。
4. 020在25张JPEG上过度拒绝，不能调参后直接宣称泛化；需要按物理零件分折且人工确认混合配对。
5. 性能P95增量需在负载受控环境重新成对测量。
6. part-006保持封存，禁止读取、重跑或调参。

## SpecKit一致性分析

implement后重新检查spec.md、plan.md、tasks.md、配置/诊断契约和实现：33/33项FR与13/13项SC均有任务、
测试或明确BLOCKED证据；43/43项任务均已执行。未发现会导致默认行为
改变、固定角屏蔽、真值泄漏或main误合并的Critical/High矛盾。配置术语已统一为fixture_shadow_model与
sidewall_source_consistency，结果诊断使用fixtureShadowEvidence与grooveSourceConsistency。唯一未关闭的工程门是
SC-012端到端P95环境证据；唯一未关闭的业务门是Mac原始BMP人工标签与混合配对复核，均已保留为BLOCKED，
没有通过放宽阈值或宣称准确率规避。

结论：020是默认关闭、可审计、fail-closed的实验框架；具备推送功能分支供Mac验证的工程条件，但不具备合入main、
默认启用、生产精度或准确率声明条件。

实现提交269b35c已推送到origin/020-fixture-shadow-groove-consistency；main与origin/main保持04d1796，未合并。
