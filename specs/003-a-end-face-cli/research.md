# Research: A 端面独立检测 CLI

## Decision 1: 权威检测实现

- **Decision**: 原样复用桌面 `算法.zip` 中 A 端面的 `repeatability_evaluation.py`。
- **Rationale**: 用户明确要求不重写检测核心；该文件已经包含参考模型、配准、圆/边界检测与量测。
- **Alternatives considered**: 复用远程历史适配器；其来源哈希不同且只暴露姿态相关函数，因此不采用。

## Decision 2: 集成边界

- **Decision**: 核心作为仓库内只读模块保存，独立 CLI 只调用 `build_reference_model` 和
  `detect_measurements`。
- **Rationale**: 无机器绝对路径依赖，仍可用 SHA-256 证明核心没有被重写。
- **Alternatives considered**: 运行时动态加载桌面绝对路径；跨服务器和 Mac 不可移植。

## Decision 3: JSON 数值策略

- **Decision**: 保留核心全部量测字段，将非有限数值规范化为 `null`。
- **Rationale**: 桌面核心用非有限值表达检测缺失，但标准 JSON 不允许 `NaN/Infinity`。
- **Alternatives considered**: 删除字段；会丢失输出结构与诊断上下文。

## Decision 4: 大文件策略

- **Decision**: 标注、参考图、目标图和归档均外置；仓库只保留来源哈希、代码和小型契约。
- **Rationale**: 满足数据治理要求并避免 Git 历史膨胀。
- **Alternatives considered**: Git LFS；本轮没有授权引入新的存储和依赖。
