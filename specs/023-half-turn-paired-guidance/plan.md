# Implementation Plan: 180°双拍槽姿态初版

**Branch**: `023-half-turn-paired-guidance` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

## Summary

在不改动单帧圆/槽算法的前提下，复用021候选提取和环形匹配，新增方向无关的固定180°双拍编排及统一单图/双图引导结果。双图以第二拍为当前姿态，第一拍仅互证或在第二拍不可用时传播；所有功能默认关闭、非权威、PLC阻断。

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: 标准库；复用现有slot_pose模块
**Storage**: JSON/JSONL，图片及运行证据Git外
**Testing**: unittest、jsonschema（可选依赖）
**Target Platform**: Linux服务器与Mac离线CLI
**Project Type**: Python算法库与CLI
**Performance Goals**: 纯编排单pair P95 <20ms，不含单帧图像检测
**Constraints**: 不使用真值运行时、不放宽检测阈值、不读取sealed part-006、不修改PLC/main
**Scale/Scope**: 单图或一次双图；每帧候选上限16

## Constitution Check

- 规格先行：PASS，FR/SC/任务可追踪。
- 坐标契约：PASS，x右/y下、正时针、负Y基准、180°方向无关均版本化。
- 安全失败：PASS，零解/多解/遮挡/输入错误均不给调整量。
- 数据溯源：PASS，pairId、captureIndex、SHA及Git外证据。
- 模块化：PASS，复用单帧payload和021 matcher，不复制圆/槽算法。
- Phase 1复核：PASS，无Constitution豁免。

## Design Flow

1. 单图入口校验单帧结果，可靠时直接复用其当前角和闭环引导公式。
2. 双图入口枚举两帧候选，将第二拍候选统一减180°映射回第一拍零件坐标。
3. 使用角残差、形状/剖面及单帧usable证据选择唯一解释；固定相机阴影不会满足半圈运动。
4. 第二拍usable时直接输出；仅第一拍usable时加180°传播到位置2并明确标来源。
5. 输出一个位置2调整量；所有候选、归一化角和失败检查保留用于诊断。
6. 后续若暴露圆/槽视觉根因，先以少量物理零件复现并只读核对yyh/gyj实现；本023不修改视觉算法。

## Project Structure

```text
specs/023-half-turn-paired-guidance/
algorithms/slot_pose/half_turn_guidance.py
tools/run_half_turn_guidance.py
contracts/half-turn-guidance-*.schema.json
config/half-turn-guidance.example.json
tests/test_half_turn_guidance.py
```

**Structure Decision**: 新模块包裹021纯候选能力；不修改或复制单帧检测链。
