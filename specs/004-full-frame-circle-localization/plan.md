# Implementation Plan: 全画面壳体外圆唯一定位

**Branch**: `003-a2-paired-notch-stability` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-full-frame-circle-localization/spec.md`

## Summary

在当前`single_real_groove`运行路径前增加版本化全画面粗定位层：对单次解码、平滑后的图像建立低分辨率视图，使用自适应二值化和连通区域几何生成有限圆候选；每个候选只进行稀疏的锁定gyj外缘射线评估，去重后通过显式质量与最佳/次佳差距选择唯一候选；仅唯一胜出者进入现有720射线物理外圆精修。无候选、候选溢出、候选不唯一或最终精修失败均在槽识别前fail-closed。显式ROI、legacy、paired和v2顶层契约保持兼容。

## Technical Context

**Language/Version**: Python 3.12（项目锁定`>=3.12,<3.13`）
**Primary Dependencies**: NumPy 2.4.4、Pillow 12.2.0；只读动态复用锁定gyj A端面源码SHA-256，不增加OpenCV/SciPy/模型运行时
**Storage**: 配置JSON、Manifest JSON、结果JSONL和Git外审阅JPEG/CSV/JSON；无数据库
**Testing**: Python `unittest`、显式`jsonschema`契约门、合成图回归、Git外25张A2 JPEG成对回放
**Target Platform**: 当前Linux服务器离线批跑，后续Mac原始BMP验收；首版CPU串行
**Project Type**: Python算法库与CLI/批处理工具
**Performance Goals**: 当前服务器完整单图P95≤2.5秒、最大≤4秒、串行吞吐≥0.3张/秒；定位新增P95预算≤0.8秒
**Constraints**: 峰值进程内存≤1.5 GiB；单图只解码/平滑一次；候选数有硬上限；媒体/私有路径不入Git；不修改只读gyj、其他137工作区、PLC或上位机
**Scale/Scope**: 25张5472×3648 JPEG开发诊断、3张对应原始BMP、1张同源BMP人工圆/槽开发参考、0张同图JPEG正式标注；完整500正常/201坏图和正式truth仍在服务器外

## Constitution Check

*GATE: Phase 0前通过；Phase 1设计后复核通过。*

- **I 规格先行与场景闭环 — PASS**：004只覆盖首要瓶颈，FR-001～FR-020和SC-001～SC-008可追踪到任务与测试；不扩展85度或PLC业务。
- **II 坐标系与姿态契约明确 — PASS**：粗候选继续使用原图左上原点、右X/下Y、像素单位；搜索窗口使用归一化坐标；最终角度契约不变。
- **III 质量评估与安全失败 — PASS**：候选、唯一性和最终物理圆分层门控；任何失败均阻止槽与角度，不提供旧值、零值或粗圆回退。
- **IV 数据溯源与可复现验证 — PASS**：外置数据用Manifest/内容哈希，报告算法/配置/环境/阶段耗时；媒体不入Git。
- **V 模块化与集成可控 — PASS**：新模块只负责粗候选和选择，最终拟圆继续委托锁定gyj；适配器编排、结果契约和审阅工具分离。
- **工程约束 — PASS**：无新依赖；性能、吞吐、稳定性和资源均有开发门；生产门限仍记录为B-004。

## Phase 0: Research Decisions

调研结论详见[research.md](research.md)。关键决策：

1. 不对多个全尺寸ROI重复执行`estimate_global_transform`，避免每个窗口重复720外圆、720内孔、polar和notch链。
2. 不引入Hough/OpenCV或训练模型；当前只有25张派生JPEG和1张人工参考，不足以证明新增依赖必要。
3. 使用低分辨率Otsu阈值与连通区域外接框产生粗候选，候选几何只用于提议，不能成为最终圆。
4. 使用锁定gyj`outer_boundary_edge_point`和`robust_fit_circle`做180射线候选验证及最终720射线精修，不复制圆拟合实现。
5. 粗候选若超过上限、没有候选或质量差距不足立即失败；禁止默认选最左、第一或最接近85度的候选。

## Phase 1: Design

### Data Flow

```text
decode + blur once
  → downsampled grayscale view
  → adaptive threshold + connected components
  → bounded coarse circle proposals
  → sparse gyj radial-edge assessment per proposal
  → deduplicate physical-circle hypotheses
  → unique best/second decision
  → one 720-ray gyj physical-circle refinement
  → existing polar/groove recognition/subpixel angle pipeline
```

失败流：

```text
invalid config/input → INPUT_INVALID
0 surviving hypotheses → HOUSING_CIRCLE_NOT_FOUND
candidate overflow or insufficient margin → HOUSING_CIRCLE_AMBIGUOUS
winner final refinement rejected → PHYSICAL_OUTER_CIRCLE_FAILED
any failure → no angular profile, no groove role, no angle, valid=false
```

### Selection and Scoring

- 连通区域仅以外接框中心/尺度、宽高比、填充率、边界余量和配置中心范围产生提议。
- 对每个提议以180个稀疏角调用gyj外缘点与robust fit，得到内点率、角覆盖、P95残差、圆心偏移和半径比。
- 先按精修圆心/半径比例去重，再对通过粗质量门的簇排名。
- 评分由版本化的覆盖、内点、残差和先验一致性权重组成，所有分量进入诊断。
- 只有唯一簇，或最佳分数高于第二候选达到配置差距时才能继续；候选数量溢出在任何昂贵精修前失败。
- 最终720射线门沿用现有`gyj-outer-boundary+slot-quality-v2`，不因粗筛结果降低门限。

### Contracts

- 现有`slot-pose-result/2`顶层不升版。
- 新增`diagnostics.circleLocalization`，契约见[contracts/full-frame-circle-localization.md](contracts/full-frame-circle-localization.md)。
- 根配置Schema新增可选`detector.full_frame_circle_locator`；与`face_search_roi_normalized`互斥，首版只允许`single_real_groove`启用。
- 新增错误码`HOUSING_CIRCLE_NOT_FOUND`、`HOUSING_CIRCLE_AMBIGUOUS`；现有`PHYSICAL_OUTER_CIRCLE_FAILED`继续表示唯一候选的最终精修失败。
- 审阅工具向后兼容：不存在新诊断时按旧行为渲染；存在时画所有粗/稀疏候选及winner。
- 真实验收增加逐图LabelMe索引契约：人工圆、真实槽、图像哈希、人员/版本和复核状态缺一不可；未复核模板只能用于待办管理。

### Performance and Batch Reuse

- 候选发现在缩小视图运行，不创建多个5472×3648 `float64`掩膜。
- 每个候选稀疏射线数和候选总数有配置硬上限；只对winner进行一次720射线精修。
- 批处理复用一个已校验的适配器/参考模型，仍在批前、逐图结束和批后核对锁定资产。
- 阶段耗时使用单调时钟记录；批次报告冷启动、稳定态P50/P95/max、墙钟吞吐和峰值RSS，审阅渲染单独计时。

### Verification Strategy

1. TDD单元：Otsu亮度缩放、连通区域、可变尺度、遮挡、裁切、无圆、双圆、候选溢出、去重、分数差距和非有限配置。
2. 委托测试：稀疏及最终阶段所有边缘决策/拟合仍调用锁定gyj函数，失败不触发后续。
3. 集成测试：1个壳体+强工装选择壳体；0/多个候选返回稳定错误；顶层角为空。
4. 回归：全量unittest、Schema、CLI、批量继续、legacy 72角、paired、ROI 25/25、1真槽+2阴影25/25、21张现有亚像素成功。
5. 真实数据：同一25张全画面与ROI成对运行，Git外输出逐图圆差、候选联系表、失败分布、阶段耗时与资源；单人工BMP作非生产参考。
6. 标注门：为25张生成Git外标注索引/空白LabelMe模板；同源BMP参考不得自动转正为JPEG truth。严格准确率验收只接收图像哈希一致、人工复核且独立于算法的标注，逐图输出人工/自动叠加及圆心、半径、槽角差。

## Project Structure

### Documentation (this feature)

```text
specs/004-full-frame-circle-localization/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── full-frame-circle-localization.md
│   └── real-case-annotation.md
└── tasks.md
```

### Source Code (repository root)

```text
algorithms/slot_pose/
├── full_frame_circle_locator.py
├── physical_outer_circle.py
├── legacy_adapter.py
├── contract.py
└── main.py

contracts/
├── slot-pose-config.schema.json
└── slot-pose-result.schema.json

config/
├── inspection.example.json
└── README.md

tools/
├── run_slot_pose_batch.py
├── prepare_real_case_annotations.py
├── evaluate_annotated_real_cases.py
├── render_slot_pose_review.py
└── summarize_slot_pose_diagnostics.py

tests/
├── test_full_frame_circle_locator.py
├── test_real_case_annotations.py
├── test_physical_outer_circle.py
├── test_legacy_adapter.py
├── test_slot_pose_contract.py
├── test_slot_pose_batch.py
├── test_slot_pose_review.py
└── test_slot_pose_diagnostic_summary.py
```

**Structure Decision**: 保持单一Python算法/CLI仓库；粗定位新增独立模块，最终拟圆不复制，配置、编排、批处理和审阅分别在现有边界内增量修改。

## Post-Design Constitution Re-check

全部门禁继续通过。方案没有以业务假设代替选圆唯一性，没有削弱质量门，没有引入不可溯源模型或新硬件依赖；候选诊断、配置版本、外置数据校验和、性能与资源报告均进入任务。无须记录复杂度豁免。

## Complexity Tracking

无Constitution违例或豁免。
