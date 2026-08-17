# Implementation Plan: D7长范围同语义直边支持

**Branch**: `main` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/023-d7-long-paired-support/spec.md`

## Summary

复用yyh/gyj v5已有的“沿直边布置多剖面并拟合直线”搜索结构，但不复用其单一最强梯度作为正式物理边界。
当前正式A/B直线和D7交点全部冻结；适配层沿窄颈方向移动现有双跃迁剖面窗口，收集通过原极性、峰值、
边带宽度和3px残差门的中点。只有A/B两侧都从原支持末端连续向外增长时，才把新增点投影到冻结直线以
延长审核线段。任何单侧中断、跨间隙孤立点或竞争层均停止扩展，不改变D7/Phi数值和有效状态。

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: 项目已有NumPy、Pillow；不新增OpenCV或其他依赖

**Storage**: 版本化JSON结果和LabelMe审核输出；原图、JSONL和运行产物仓库外

**Testing**: `unittest`测试先行、权威单图、581/582/981、010/030/050代表帧、5组100帧回归

**Target Platform**: Linux服务器运行与Mac离线视觉审核

**Project Type**: Python算法适配层和离线审核CLI

**Performance Goals**: 扩展只对正式D7成功帧执行，100帧可完成；记录相对022批次的mean/p95耗时变化

**Constraints**: 不改`algorithms/hole_2/main.py`、配置、Schema、Phi、门限或业务测量列；不读目标真值做运行时决策

**Scale/Scope**: 唯一权威真值1张、人工诊断581/582、代表181/581/582/981、5个显式20帧组共100张

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- I 规格先行：023的需求、风险、任务、测试和外置结果均有稳定编号及路径，PASS。
- II 核心原样复用：冻结`algorithms/hole_2/main.py`，仅在适配层调用其公开检测原语，PASS。
- III 可复现输出：保留输入/模板指纹和像素单位；新增诊断只含有限数值或`null`，PASS。
- IV 安全失败：扩展不参与measurementValid，不跨间隙、不升级v6 REVIEW，PASS。
- V 数据最小化：BMP、人工JSON、JSONL、JPEG/PNG和运行目录全部Git外置，PASS。
- 不输出毫米或生产OK/NG，不读取目标真值作为检测输入，PASS。

## Design

### 1. Frozen measurement geometry

正式paired-transition检测完成后冻结：A/B共同法向、两条直线偏移、公法线交点、D7值及全部质量状态。扩展过程
只能改变`segmentPointsPx`和独立审核支持字段，任何异常都回到022原显示段，不能使失败D7恢复有效。

### 2. Reused moving-strip candidate generation

从yyh/gyj既有算法复用“沿直边移动横向剖面带”的候选生成方式。移动中心取现有正向
`band_offsets_target_px`，每个窗口仍调用当前双跃迁检测：每条剖面必须找到方向相反且宽度合格的两个峰，
物理点取二者中点。即使某个移动窗口整体拟合失败，也只允许读取它已经通过逐剖面极性/峰值/宽度检查的原始
中点，再对冻结直线执行原3px残差检查。

### 3. Continuous dual-side corridor

主窗口朝窄颈方向的已验收点构成每侧基线。新增点按沿程坐标排序、去重，并从基线末端向外连续推进；最大允许
相邻间隔由现有剖面采样间距导出，不增加人工像素补偿。A/B必须同时获得至少一个连续新增区间；若任一侧中断，
两侧都保持原段。远端重新出现的孤立簇只记录为rejected，不得跨间隙拼接。

### 4. Projection and evidence layers

新增支持点保留原图坐标和对应跃迁对。显示端点由主paired中点与连续新增点在冻结直线上的投影极值生成；直线方程
不重算。结果明确分层：

- `pointsPx` / `transitionPairsPx`: 原正式主窗口paired证据；
- `supportPointsPx` / `supportTransitionPairsPx`: 长范围连续paired支持；
- `lineEquation`: 冻结正式直线；
- `segmentPointsPx`: 两类证据投影后的有限审核段；
- `measurementAnnotation`: 原公法线与原D7值。

### 5. Renderer and fallback

正式A/B仍为橙色直线，局部放大中用小型标记显示长范围支持点并在LabelMe line flags写入支持模式/点数。
v6回退保持紫色REVIEW、`evidenceAvailable=false`，不得调用长范围扩展升级证据。Phi渲染完全不改。

### 6. Validation

- 合成测试覆盖安全延伸、单梯度偏层、单侧中断、跨间隙孤立点、竞争层和数值冻结。
- 581/582必须记录B侧中断并拒绝错误长线；981的双侧连续范围预期从约34px增长到至少48px。
- 权威真值继续D7<=2px、Phi<=1px；100帧状态及D7/Phi数值逐帧与022一致。
- 新旧审核图和批次结果写到仓库外，Mac最终负责视觉复核。

## Project Structure

### Documentation (this feature)

```text
specs/023-d7-long-paired-support/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/d7-long-support-contract.md
├── checklists/requirements.md
├── analysis.md
└── tasks.md
```

### Source Code (repository root)

```text
algorithms/hole_2/current_capture.py
tools/render_hole2_batch_report.py
tools/render_hole2_batch_changes.py
tests/test_current_capture_registration.py
tests/test_current_capture_contract.py
tests/test_hole2_batch_report.py
tests/test_hole2_batch_review.py
```

**Structure Decision**: 只扩展既有适配层审核证据和renderer；冻结核心、配置、Schema、Phi和业务值，不新增依赖。

## Constitution Re-check

Phase 1设计后仍无Constitution例外。移动窗口调用冻结检测原语；扩展不参与测量状态或数值；v6 review不升级；
所有真实资产与输出外置。

## Complexity Tracking

无Constitution例外。
