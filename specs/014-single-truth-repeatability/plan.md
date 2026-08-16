# Implementation Plan: 单一真值与无标注重复性诊断

**Branch**: `main` | **Date**: 2026-08-15 | **Spec**: `spec.md`

## Implementation order

1. 测试先行冻结显式组失败段、manifest完整性、population/role隔离和真值FAIL不可覆盖。
2. 修复现有批量诊断的显式组失败段。
3. 新增只读研究CLI：合并多个batch JSONL，严格映射外置manifest，读取已有单图验收报告。
4. 输出cohort统计、capture-group静态重复性（样本标准差/6σ/range/MAD）、逐帧中位数偏差及
   source/recovery/failure分布。
5. 用外置服务器小样运行；holdout不作为实现输入，defective单列。
6. 运行全套unittest、compileall、SpecKit analyze、diff和大文件审计。

## Safety

- 不修改运行时算法、配置、Schema或门限。
- 不读取图片/目标标注，不输出mm或生产判定。
- 输出必须在工作树外，Git只保存源码、测试和SpecKit文档。
- 无标注数据只产生diagnostic，不产生精度PASS。
