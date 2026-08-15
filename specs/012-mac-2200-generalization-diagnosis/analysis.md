# SpecKit Analyze: Mac 2200 泛化退化诊断

**Analyzed**: 2026-08-15
**Status**: Pure diagnosis complete; implementation intentionally blocked

## 1. Cross-artifact consistency

- `spec.md` 的16项FR映射到 `tasks.md` T001–T031；本轮范围对应T001–T020，未来实现明确阻塞。
- `research.md` 分别回答A相位分数语义、B geometry硬拒绝、C尺寸7上游耦合、D 105张分布、
  E修复候选/测试/风险/Mac门。
- `plan.md` 把完成的纯诊断Phase 0与未授权的测试/实现Phase 1–2分开，没有把候选写成既成行为。
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
| strict cohort split | all artifacts | covered |
| no runtime changes in diagnosis | scope/stop gates | covered |

## 5. Safety and constitution review

- 未使用或提交目标图片、LabelMe、JSONL或2200张运行输出。
- 未提出文件名/hash特判、310/541.13/12.2硬编码、固定像素补偿或输出拉向标称值。
- 未把全局降低0.35或直接放宽0.08列为方案。
- sequence suffix仅用于簇描述，明确禁止推断20帧样品组。
- defective增益未用于接受normal退化。
- 本阶段不修改核心、适配层、配置、Schema、测试或运行时质量门。

## 6. Testability review

未来测试矩阵同时覆盖：

- legacy强边；
- phase分数较弱但多证据一致；
- 错误极性、低覆盖、少点、高残差和越界；
- geometry离群但无独立错边证据；
- geometry离群且存在独立错边证据；
- D7上游连带与自身检测失败；
- 最新唯一真值单图、分层shadow、9帧、normal 2000、defective 200和比例离群。

这些测试可以在不向运行时提供目标标注的前提下执行；只有离线单图验收读取最新真值。

## 7. Open evidence gaps

1. 105张delta未导出通用 `recoveryPass`，只知道 `phaseFallback=null`；下一轮诊断应补字段，
   不能从source猜恢复分支。
2. 36张geometry rejected中另6张不在old-valid→new-invalid集合，当前delta不足以逐图归类。
3. normal 2000没有逐图真值，不能证明105张全部正确或36张全部错误。
4. 文件名连续簇不是重复样品manifest，不能据此计算样品级稳定性。
5. candidate normal mean/p50/p95耗时均上升，后续接受除检测率外还需继续报告性能。

这些缺口不阻断诊断结论，但阻止直接把全部lost强制恢复。

## 8. Analyze verdict

012文档在需求、证据、代码历史、候选、测试和停止条件之间一致，没有发现应先改运行时才能
完成的阻断项。结论支持进入“测试先行的定向修复”评审，但本轮授权只到纯诊断提交，故实现
保持blocked并在推送文档后停止。
