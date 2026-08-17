# Implementation Plan: 单拍视觉分层根因诊断

**Branch**: `024-single-shot-visual-root-cause` | **Date**: 2026-08-17

## Summary

复用已有022结果和review renderer构建9张小样本审阅包，建立分层根因表；并行只读核对yyh/gyj圆与边缘实现。首轮不改核心算法和阈值，人工证据足够后再追加Spec任务。

## Technical Context

- Python 3.10+、现有JSONL/review工具、Git外BMP。
- 不新增依赖，不重跑140/700张。
- 数据根只在运行命令中出现，不进入Git。

## Constitution Check

- Spec先行、坐标与状态契约、安全失败、数据溯源、模块复用：PASS。
- 大图Git外、sealed隔离、PLC/main不动：PASS。

## Flow

1. 从冻结三折manifest和022结果按SHA选择9张。
2. 用现有render工具生成审阅包，不重算检测。
3. 提取各阶段门指标并形成根因矩阵。
4. 只读审计yyh/gyj可复用做法。
5. 将“可直接修复”与“需人工裁决”分开；未裁决不改算法。
6. 将动态加载gyj绝对源码路径改为本仓库内唯一模块的可选加载模式；外部文件模式仅作兼容。
7. 本地模块与Git外参考标注/图像分开管理：前者随代码合并，后者随部署资产包供应并用SHA锁定。
