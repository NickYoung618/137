# SpecKit Analyze: Mac 2200 泛化退化诊断

**Analyzed**: 2026-08-15
**Status**: Directed implementation analyzed; Mac 2200 acceptance pending

## 1. Cross-artifact consistency

- `spec.md` 的21项FR映射到 `tasks.md` T001–T037；诊断、A1/B1实现和离线审核工具均已完成，
  只有依赖Mac 2200外置资产的T031未完成。
- `research.md` 分别回答A相位分数语义、B geometry硬拒绝、C尺寸7上游耦合、D 105张分布、
  E修复候选/测试/风险/Mac门。
- `plan.md` 保留纯诊断Phase 0的历史边界，并记录明确授权后的测试先行实现结果和Mac停止门。
- 所有文档统一使用normal 2000作为验收组，defective 200只作独立观察。
- 最新唯一真值单图门在spec、plan和tasks中一致为尺寸7 `<=2 px`、Phi直径 `<=1 px`。

## 2. Evidence consistency

### Summary reconciliation

- baseline normal：registration `1962`、7 `1863`、Phi `1922`。
- candidate normal：registration `1985`、7 `1772`、Phi `1826`。
- delta逐图：registration `+23`；7 lost/gained `136/45`，净 `-91`；Phi lost/gained
  `135/39`，净 `-96`。与summary完全一致。
- 两组均无执行错误。

### Root-cause reconciliation

- 105张Phi lost为 `edge_peak_below_gate`；新phase peak p50 `0.34217` 对0.35，其他相位质量
  p50为 residual `0.677 px`、points `196`、polarity `1.0`、coverage `0.9799`。
- 36张candidate normal geometry rejected，只有30张进入old-valid→new-invalid lost；该区别在
  spec/research/tasks中保持。
- 尺寸7 lost `136 = 105 + 30 + 1`，说明自身paired/tangent新增失败不是净退化主体。

未发现normal与defective混算、lost/gained算术冲突或把单图精度外推到批量的表述。

## 3. Code-history findings

### Finding A — confirmed

phase候选的 `edge_peak` 是一维有符号相位峰统计，legacy候选的 `edge_peak` 是二维梯度幅值
圆周统计；当前最终门对二者使用同一 `min_edge_peak_normalized=0.35`。这是语义复用错误，
不是“105张自然略低于同义门”的证据。

### Finding B — confirmed with lineage correction

`79aa6a4` 没有运行时geometryConsistency。硬拒绝由 `526c080` 引入并由 `3ee4b4f` 继承，
不是011单独新增。36张缺少逐图人工真值，不能视为已证明错边。

### Finding C — confirmed

尺寸7新增lost仅1张来自自身检测；135张由Phi上游或组合geometry门造成。不得通过放宽尺寸7门
来解决这91张净下降。

## 4. Requirement coverage

| Requirement group | Evidence/design coverage | Status |
|---|---|---|
| A phase score semantic mismatch | research §2、plan 1A、tasks T006/T021/T022 | covered |
| B geometry diagnostic vs hard reject | research §3、plan 1B、tasks T008/T009/T023 | covered |
| C D7 upstream coupling | research §4、plan 1C、tasks T010/T024 | covered |
| D 105 frame distributions | research §2 sequence/source/fallback/ratio/quality | covered |
| E fixes/tests/risks/Mac gate | research §5–6、plan matrix、tasks T021–T031 | covered |
| strict cohort split | all artifacts及审核工具group+文件名配对 | covered |
| 离线old/new人工审核 | spec US5/FR017–021、tasks T032–T037、quickstart | covered |
| diagnosis与授权实现边界 | scope/stop gates及两次里程碑提交 | covered |

## 5. Safety and constitution review

- 未使用或提交目标图片、LabelMe、JSONL或2200张运行输出。
- 未提出文件名/hash特判、310/541.13/12.2硬编码、固定像素补偿或输出拉向标称值。
- 未把全局降低0.35或直接放宽0.08列为方案。
- sequence suffix仅用于簇描述，明确禁止推断20帧样品组。
- defective增益未用于接受normal退化。
- 复用核心与配置未修改；授权后只修改current-capture适配层和结果Schema以分离证据语义，
  legacy/geometry数值门均保持，测试冻结这些值。
- 审核工具只读old/new预测JSONL和外置图片，不接受目标标注参数，也不写入Git工作树。

## 6. Testability review

已执行的测试矩阵覆盖：

- legacy强边；
- phase分数较弱但多证据一致；
- 错误极性、低覆盖、少点、高残差和越界；
- geometry离群但无独立错边证据；
- geometry离群且存在独立错边证据；
- D7上游连带与自身检测失败；
- 最新唯一真值单图、9帧控制和审核工具；normal 2000、defective 200及比例离群仍待Mac T031。

这些测试可以在不向运行时提供目标标注的前提下执行；只有离线单图验收读取最新真值。

## 7. Open evidence gaps

1. 105张delta未导出通用 `recoveryPass`，只知道 `phaseFallback=null`；下一轮诊断应补字段，
   不能从source猜恢复分支。
2. 36张geometry rejected中另6张不在old-valid→new-invalid集合，当前delta不足以逐图归类。
3. normal 2000没有逐图真值，不能证明105张全部正确或36张全部错误。
4. 文件名连续簇不是重复样品manifest，不能据此计算样品级稳定性。
5. candidate normal mean/p50/p95耗时均上升，后续接受除检测率外还需继续报告性能。

这些缺口不阻断诊断结论，但阻止直接把全部lost强制恢复。

## 8. Post-implementation re-analysis

- A1与诊断根因一致：配置中的legacy `0.35`未变；phase多证据与legacy幅值门分别命名、分别
  判定，契约输出可审计。
- B1没有放宽`0.08`或删除离群信息；硬拒绝新增独立风险证据要求，单纯未经真值证实的比例
  离群不再清空两个已通过自身图像门的测量。
- C1未实施，避免把未验证的Phi几何hint引入D7；D7自身质量门和v6回退规则没有放宽。
- 单元负例覆盖错误极性、高残差、少点和fallback不绕过legacy门；Schema要求geometry决策、
  离群与佐证字段一致。
- 最新唯一真值单图和9帧控制通过，但105/36分层和normal 2000检测率只能由Mac外置资产确认。
- 离线审核工具不接受目标标注参数，按group+文件名配对old/new，防止跨组混合；默认只渲染
  状态变化帧，显式帧模式可审核控制帧。PNG与LabelMe JSON均强制输出到工作树外。
- 外置9帧小样匹配9帧、识别4帧状态变化，并成功为指定控制帧620生成一张3072×2048叠加图
  和包含old/new尺寸7、Phi四个预测shape的LabelMe JSON。

## 9. Analyze verdict

012的诊断、测试、实现和契约一致，没有发现通过降低全局门限、读取目标真值或修改输出值来
追求检测率的行为。服务器门禁支持将本候选推送给Mac执行T031，但不支持提前声称normal 2000
达标。最终接受仍要求registration `>=1962`、7 `>=1863`、Phi `>=1922`、比例离群不增加且
defective 200单列报告。
