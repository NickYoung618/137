# Implementation Plan: 真槽同源性误拒裁决

**Branch**: `022-source-consistency-adjudication` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/022-source-consistency-adjudication/spec.md`

## Summary

在现有双壁同源性判定之后增加默认关闭的二级裁决。原判定及0.12对比度门不改写；只有原失败精确为contrast-only、所有其他原检查通过、严格端点结构证据也通过时，二级裁决才在显式实验配置下让本帧继续图像姿态计算。其他类型全部fail-closed，PLC仍阻断。

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: 现有NumPy/Pillow检测栈；裁决本身只消费已有标量diagnostics

**Storage**: Git内版本化配置/Schema/测试；Git外BMP、LabelMe、JSONL和评估报告

**Testing**: `unittest`、Draft 2020-12 JSON Schema、冻结JSONL及原始BMP离线回放

**Target Platform**: Ubuntu服务器与macOS独立回放

**Project Type**: 离线/运行时图像算法库与CLI

**Performance Goals**: 裁决纯标量计算P95增量`<=5 ms`，不增加图像解码、大图复制或射线采样

**Constraints**: 默认关闭；不改原0.12门；不读人工真值/runtime身份；part-019保持负例；main/PLC不改

**Scale/Scope**: 服务器现140张非sealed A2 BMP三折回放；145一张正式角真值，145/147两张清洁槽像素证据，part-019二十帧混合负例

## Constitution Check

- **I 规格先行**: PASS。正例、负例、运行时输出和不升权边界已分需求编号。
- **II 坐标契约**: PASS。沿用`image-y-down-clockwise-signed/1`，不新增坐标转换。
- **III 质量与安全失败**: PASS。仅精确contrast-only+严格二级证据可override；其他全拒绝。
- **IV 数据溯源**: PASS。真值和runtime以SHA离线绑定，不进入运行时。
- **V 模块化**: PASS。独立标量裁决模块接在现有source-consistency与pose之间，不复制检测链。

## Project Structure

### Documentation

```text
specs/022-source-consistency-adjudication/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── evidence.md
├── contracts/runtime-adjudication.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code

```text
algorithms/slot_pose/
├── source_consistency_adjudication.py
├── contract.py
└── legacy_adapter.py
config/
└── source-consistency-adjudication.example.json
contracts/
├── slot-pose-config.schema.json
└── source-consistency-adjudication.schema.json
tests/
├── test_source_consistency_adjudication.py
├── test_single_real_groove.py
└── test_slot_pose_contract.py
tools/
├── prepare_source_consistency_adjudication_config.py
└── summarize_source_consistency_adjudication.py
```

**Structure Decision**: 在现有`algorithms/slot_pose`中新增纯函数裁决模块，适配器只负责组装原/有效状态与决定是否继续姿态链。离线汇总工具只读JSONL，不读人工几何。

## Data Flow

1. 现有检测链产生物理外圆、唯一真槽候选、两壁精修和`OriginalSourceConsistency`。
2. 若新配置缺失/关闭，完全沿用原路径。
3. 若开启，裁决模块仅检查原数值证据，产生`SourceConsistencyAdjudication`。
4. `ACCEPTED_OVERRIDE`仅改变本帧`effectiveStatus`；原source payload保留。
5. 适配器只在effective accepted时继续单槽角度与图像引导；其他阶段门仍照常执行。
6. 离线工具汇总override/拒绝分布；人工真值由既有评估器独立比较。

## Test Strategy

- 纯函数：状态、字段完整、有限值、精确失败集合、边界、原证据不变和`<=5 ms`P95。
- 运行时集成：开关关闭不回归；开启洁净contrast-only可继续pose；混合/多失败仍无角。
- Schema：配置和诊断状态一致性。
- 真实数据：服务器先用现140张三折；part-019必须20/20仍拒绝，part-008单独报告，其他组不强行通过。Mac用同源BMP独立复现。
- 精度：只用145长弧真值评估已恢复候选角；147不评价最终角精度。

## Complexity Tracking

无Constitution违反。新模块不引入依赖、并发、模型或第二条图像处理链。
