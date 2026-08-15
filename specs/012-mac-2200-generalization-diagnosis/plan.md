# Implementation Plan: Mac 2200 泛化退化诊断

**Branch**: `main` | **Date**: 2026-08-15 | **Spec**: `specs/012-mac-2200-generalization-diagnosis/spec.md`

## Summary

本阶段先把Mac 2200张外置证据转化为可追溯根因，并在获得明确授权后按测试先行实施A1/B1。
normal 2000仍是唯一检测率验收组，defective 200独立观察；服务器结果不能替代Mac验收。

## Technical Context

**Language/Version**: Markdown诊断；后续候选仍是Python 3.11+

**Primary Dependencies**: 外置批量summary/delta、Git历史、现有NumPy/Pillow检测实现

**Storage**: Git仅保存小型SpecKit文档；外置JSON/图片/JSONL不入库

**Testing**: 本阶段为证据复算、源码历史审计、`git diff --check`；后续为unittest、真实单图、
9帧和Mac 2200

**Target Platform**: Linux诊断与Mac外置批量复测

**Project Type**: Python库/CLI的诊断增量

**Performance Goals**: 本阶段不改性能；后续报告normal mean/p50/p95，避免当前约15.8% mean增加
被忽略

**Constraints**: 无运行时真值、无全局门限放宽、无标称值/固定补偿、严格分组、先测试后实现

**Scale/Scope**: normal 2000 + defective 200；delta changedFrames 256

## Constitution Check

- **规格先行与追踪**：通过 `spec.md` FR、`research.md` 根因、`tasks.md` 任务矩阵建立追踪。
- **检测核心复用**：本阶段不修改 `algorithms/hole_2/main.py` 或 current-capture适配层。
- **可复现**：记录三个证据SHA、两个commit和确切组别；不把外置资产复制进Git。
- **安全失败**：修复候选不得把无效强制改有效，要求错误极性/低覆盖/高残差等负例。
- **数据最小化**：只提交五个Markdown文件。

仓库constitution标题仍写A端面，但本仓库和用户明确范围是孔2；沿用既有孔2规格的已知治理
例外，本增量不修改constitution。

## Phase 0: Completed diagnosis-only delivery

1. 冻结并校验三份外置证据SHA。
2. 分别复算normal和defective汇总，禁止overall混合验收。
3. 对105张phase lost分析分数语义、分布、连续序号簇、source/fallback和半径比。
4. 用Git历史定位geometry硬拒绝最早引入提交，并区分36 rejected与30 lost。
5. 分解尺寸7的136 lost，确认自身新增失败只有1张。
6. 输出定向候选、测试矩阵、风险和Mac接受门。
7. 只提交SpecKit文档并停止。

## Phase 1: Proposed test-first work after explicit approval

### 1A. Score-semantics characterization tests

- 冻结legacy magnitude与phase signed peak为两个字段，测试不允许交叉套门。
- 构造“phase normalized低于0.35但绝对峰、极性、残差、点数、覆盖均合格”的候选，先以
  当前行为形成红灯。
- 构造错误极性、低对比度、低覆盖、少点、高残差、中心/半径越界负例，必须继续失败。
- 锁定旧magnitude候选的0.35行为不变。

### 1B. Geometry semantics tests

- 先证明当前“比例单独超门会清空两个测量”的行为。
- 新契约应把“比例离群诊断”和“硬拒绝所需的独立错边证据”分开。
- 测试比例不能修改长度、直径或把结果拉向参考比；错误边+独立图像失败仍须拒绝。

### 1C. D7 coupling tests

- 证明phase分数语义修正后，D7不会仅因Phi错用legacy分数而丢失。
- 保持paired contour自身的点数、残差、峰值、配对宽度和平行门。
- 只有A/B仍不足时，才为只读Phi几何提示设计独立测试；不得提前实现。

## Phase 2: Proposed implementation order after tests fail

1. 实现命名分离的phase/legacy质量字段和各自门，不改legacy 0.35。
2. 实现geometry多证据策略或诊断/有效性解耦，不改0.08数值来掩盖语义问题。
3. 对105/36/尺寸7-1张做外置shadow运行，先比较逐图状态和质量，不立即宣称精度。
4. 运行最新唯一真值单图，必须保持尺寸7 `<=2 px`、Phi直径 `<=1 px`。
5. 运行9帧控制和全套unittest/compileall/Schema/大文件门。
6. 推送候选后由Mac重跑normal 2000与defective 200，严格分组出报告。

## Test matrix and acceptance

| Layer | Case | Required result |
|---|---|---|
| Unit: score | legacy magnitude正常 | 继续通过原0.35门 |
| Unit: score | phase normalized弱、但绝对峰/极性/残差/点数/覆盖/边界全部合格 | 不得因legacy 0.35单独失败 |
| Unit: score | phase错误极性或低覆盖/高残差/少点 | 明确失败，不得fallback伪恢复 |
| Unit: geometry | 两特征有效但比例离群、无其他错边证据 | 保留离群诊断，不改数值；最终是否有效按批准后的契约 |
| Unit: geometry | 比例离群且有独立错边证据 | 明确拒绝 |
| Unit: D7 | Phi仅受错误score语义影响 | 修正Phi后D7上游不再连带丢失 |
| Unit: D7 | paired contour自身失败 | 继续失败或仅走原v6质量回退 |
| Real single | 最新唯一真值 | 尺寸7误差 `<=2 px`，Phi直径误差 `<=1 px` |
| External strata | 105 phase、36 geometry、1 D7自身lost、23 registration gained | 输出逐图old/new与来源；控制注册增益不回归 |
| Mac normal | 2000好样品 | registration `>=1962`、7 `>=1863`、Phi `>=1922` |
| Mac ratio | 与基线同定义/同manifest | 比例离群不增加 |
| Mac defective | 200坏品 | 单列观察，不参与normal接受 |
| Reliability | 全量 | execution errors为0 |

## Risk controls

- **弱相位误接受**：用原magnitude seed、参考极性、绝对峰、残差、覆盖和候选一致性共同限制。
- **geometry错边漏放**：比例离群仍保留并触发审计；硬拒绝需要第二个独立图像证据。
- **D7错误上游提示**：先修A/B，只有剩余证据支持时才拆分几何hint。
- **批量过拟合**：不读取目标真值，不按文件名/hash或序号特判；序号只用于报告簇。
- **单图回归**：最新SHA锁定单图是独立硬门。
- **性能回归**：后续Mac必须同时报告mean/p50/p95，不能只看valid数。

## Project Structure

```text
specs/012-mac-2200-generalization-diagnosis/
├── spec.md
├── research.md
├── analysis.md
├── plan.md
└── tasks.md
```

**Structure Decision**: 本阶段无源码、配置、测试、契约或工具变更；五个文档构成完整诊断交付。

## Implementation outcome

- reference-phase候选使用自身的绝对峰、极性、点数、残差、覆盖和边界证据；legacy二维幅值
  seed继续单独通过原`0.35`峰值及显著性门，两类分数不再交叉比较。
- geometry `0.08`保持不变并始终输出离群诊断；只有比例离群与注册恢复、Phi legacy fallback或
  D7 v6 fallback之一同时存在时才硬拒绝。比例单证据不修改测量值。
- 未实现C1几何hint拆分；现有D7自身质量门、Phi两阶段半径搜索和注册主门保持不变。
- 最新唯一真值单图通过：尺寸7误差`0.7173203881 px`，Phi直径误差`0.1053051052 px`。
- 9帧外置诊断与上一候选状态一致；500/521/620控制帧变换和测量数值零差异。

## Stop gate

定向实现已获批准并完成。推送候选后停止在Mac T031之前；只有normal 2000达到既定三项门且
比例离群不增加，才可声明批量泛化验收通过。
