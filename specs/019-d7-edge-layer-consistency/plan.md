# Implementation Plan: D7边缘层一致性

**Branch**: `main` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

## Summary

在不改配置和D7质量门的前提下，修复paired-transition主路径失败后跳到单梯度外层的语义断裂。
仅对原成对过渡中点做失败后稳健层拟合，最终复用原支持数、残差、方向、平行度和搜索边界门。

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: NumPy, Pillow（无新依赖）

**Storage**: Git外置BMP/JSONL/评价输出

**Testing**: `unittest`、外置真实帧E2E、JSON Schema

**Target Platform**: Linux服务器与Mac离线CLI

**Project Type**: Python算法库/CLI

**Constraints**: 不改Phi、D7配置/质量门；不读holdout；不硬编码真值/文件名/像素补偿

**Scale/Scope**: 2张人工边缘层对照、20张030组、9张development/diagnostic、1张权威同图

## Constitution Check

- I 规格先行：PASS，019规格、研究、任务和测试映射后再改代码。
- II 核心复用：PASS，仅修改`current_capture.py`的独立候选层，不改权威参考资产。
- III 可复现：PASS，保留来源/恢复/质量诊断，不生成mm或OK/NG。
- IV 安全失败：PASS，所有原门不变，无主导层时拒绝。
- V 数据最小化：PASS，图片、人工JSON、JSONL和审核图不进Git。

## Project Structure

```text
algorithms/hole_2/current_capture.py
tests/test_current_capture_registration.py
tests/test_current_capture_real_e2e.py
specs/019-d7-edge-layer-consistency/
├── spec.md
├── research.md
├── analysis.md
├── data-model.md
├── contracts/d7-edge-layer-quality.md
├── plan.md
├── tasks.md
└── quickstart.md
```

**Structure Decision**: 不新增运行时模块；最小候选改动留在现有D7 current-capture适配层，测试留在既有注册/E2E套件。

## Implementation phases

1. 冻结基线和证据，完成SpecKit研究/根因分析。
2. 测试先行：主导层恢复、歧义拒绝、原成功路径不变、诊断字段。
3. 实现失败后成对过渡稳健层拟合，移除单梯度恢复的有效出口。
4. 复测581/582、030组、9帧和权威同图，对比Phi逐值不变。
5. 运行全套工程门禁和SpecKit analyze，记录结果。
