# Implementation Plan: 单人工样板驱动的无真值诊断

**Branch**: `003-a2-paired-notch-stability` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)

## Summary

在不改运行时检测的前提下，将唯一人工BMP标注的现有审阅/自动对比固化为带哈希的开发参考摘要；将Manifest批结果导出为每图可在LabelMe查看的`AUTO_`诊断。参考角只产生“观测差”，不产生其他图的误差或truth。

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Python标准库、现有Pillow/NumPy间接结果；无新依赖

**Storage**: Git外LabelMe JSON、CSV、摘要JSON；Git内仅存Schema/脱敏证据

**Testing**: `unittest`、`jsonschema`、CLI临时目录端到端

**Target Platform**: Linux服务器与Mac离线审阅

**Constraints**: 不写图像；不改人工标注；不将自动图形写成truth；输出必须在Git外；不修改运行时/不接PLC

**Scale/Scope**: 1个人工参考样本，25张无真值JPEG诊断

## Constitution Check

- **I 规格先行**: PASS；参考、无truth诊断和禁止结论分开。
- **II 姿态契约**: PASS；复用Y下半轴、顺时针正和环形差。
- **III 安全失败**: PASS；缺几何保持null，不用参考填补。
- **IV 溯源复现**: PASS；所有参考与诊断均用哈希锁定。
- **V 模块化**: PASS；新增独立离线导出器，运行时不依赖。

## Phase 0: Research Decisions

1. 不用唯一人工角作为25图共享truth；姿态可变，这会伪造误差。
2. 不向人工truth模板预填算法结果；自动诊断使用独立目录和`AUTO_`命名空间。
3. LabelMe只引用原图的相对路径，`imageData=null`；不复制大图。
4. 与参考的角差可帮助理解姿态差异，但字段和契约必须声明它不是accuracy error。

## Phase 1: Design

### Data Flow

```text
manual review + same-image runtime comparison
  -> hash consistency gate
  -> development-reference.json (offline only)

manifest + runtime JSONL + development reference
  -> one-to-one task/image/hash validation
  -> AUTO LabelMe shapes + per-image values
  -> diagnostic-index.json + diagnostics.csv
```

### Project Structure

```text
tools/export_reference_anchored_diagnostics.py
contracts/reference-anchored-diagnostics.schema.json
tests/test_reference_anchored_diagnostics.py
specs/006-single-reference-diagnostics/
```

### Verification Strategy

1. TDD覆盖参考哈希契约、安全路径、成功/失败诊断和环绕角。
2. 对现有唯一人工BMP及25张JPEG实跑，产物全部留在Git外。
3. 校验25份JSON无truth标签、无图像嵌入、无绝对路径，且字段与运行时数值一致。
4. 复跑全量测试与污染检查。

## Complexity Tracking

无Constitution违例或豁免。
