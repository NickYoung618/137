# Tasks: 孔2测量证据几何审计

- [x] T001 确认HEAD=90b0a06且工作树clean
- [x] T002 审计旧参考Phi linestrip角域和尺寸7 line语义
- [x] T003 审计current_capture数值、support points和边界数据丢失位置
- [x] T004 审计batch report与changes renderer的完整circle/单line输出
- [x] T005 分离检测失败与几何/显示错误根因
- [x] T006 复核501/520/623/775/1830/1951服务器证据
- [x] T007 记录1331/1835仅有Mac元数据、服务器无当前资产的限制
- [x] T008 提出三层证据契约和LabelMe对象命名
- [x] T009 图纸确认Phi大圆外轮廓及尺寸7窄颈两平行边垂距；最新澄清Phi只测单侧校准弧
- [x] T010 specify/clarify evidence Schema、单侧Phi弧、D7两边界证据和验收测试
- [x] T011 红灯覆盖完整circle、单dimension line和缺失证据层
- [x] T012 保留Phi实际校准弧点、内部镜像诊断与数学圆模型，不把拟合圆当轮廓
- [x] T013 保留D7 transition pairs、A/B拟合线和独立垂距标注
- [x] T014 更新batch report与old/new review为arc linestrip和三线D7证据
- [x] T015 真实唯一真值单图数值门与证据契约通过
- [x] T016 9帧非holdout诊断集复跑，500/521/620控制状态不回归
- [x] T017 全套unittest、compileall、SpecKit analyze和大文件审计
- [ ] T018 Mac视觉复核与全量回归（本轮不在服务器声称完成）
- [x] T019 记录Mac非holdout 293/51快速回归、D7三帧零证据和Phi六帧零弧缺口
- [x] T020 按负责人确认将Phi单侧校准弧定义为完整证据，不再要求镜像第二弧
- [x] T021 红灯覆盖数值有效/证据不可审解耦、单侧Phi完整性、renderer无伪造shape与琥珀警告
- [x] T022 实现`evidenceComplete`、`evidenceAuditStatus`、`evidenceAuditReason`及Schema校验
- [x] T023 batch report/review只交付单侧校准Phi弧，审核状态进入LabelMe、CSV、JSON和预览
- [x] T024 定量诊断最新人工弧的下方落点和窄颈端截短根因，不调门限或扩张角域
- [ ] T025 服务器真实单图、全套unittest、compileall、SpecKit analyze、diff/大文件门禁
- [ ] T026 提交并push origin/main，不提交外置诊断图、JSONL或LabelMe输出

第一实现阶段不得修改现有质量门；先让失败位置和实际证据可审计。
