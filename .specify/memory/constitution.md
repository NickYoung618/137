<!--
Sync Impact Report
- Version change: 2.0.1 -> 3.0.0
- Corrected project identity after a cross-repository merge replaced the slot-pose
  constitution with the unrelated A-end-face measurement constitution.
- Restored principles:
  - I. 规格先行与场景闭环
  - II. 坐标系与姿态契约明确
  - III. 质量评估与安全失败
  - IV. 数据溯源与可复现验证
  - V. 模块化与集成可控
- Removed unrelated A-end-face-only scope and desktop-core constraints.
- Added no new principle; restored the last slot-pose-specific governance text.
- Follow-up TODOs: none.
-->
# 槽姿态引导算法 Constitution

## Core Principles

### I. 规格先行与场景闭环
每项实现 MUST 关联到已评审的用户场景、验收标准和需求编号。槽的定义、引导对象、自由度、
传感器输入、现场约束或成功判据不明确时，MUST 先澄清规格，不得通过算法默认假设替代业务
决策。规格、计划、任务、测试与现场验收 MUST 可双向追踪。

### II. 坐标系与姿态契约明确
所有输入输出 MUST 明确坐标系名称、原点、轴方向、左右手系、长度和角度单位、旋转表示、
变换方向、时间戳及有效性规则。姿态输出 MUST 同时给出质量指标和适用范围。标定链、工具偏置、
坐标变换顺序和姿态约定 MUST 版本化并通过契约测试，不得依赖隐式约定。

### III. 质量评估与安全失败
算法 MUST 对输入质量、槽检测质量和姿态可信度给出可解释的质量指标。遮挡、数据缺失、匹配
歧义、标定失效或质量未达门限时，MUST 输出明确的不可引导状态和原因，不得复用过期姿态或
构造看似有效的结果。所有降级和重试策略 MUST 在规格中定义并可测试。

### IV. 数据溯源与可复现验证
原始传感器数据 MUST 保持不可变，并记录样本标识、采集条件、设备和标定版本。算法、模型、
配置、随机种子及依赖版本 MUST 随评测结果保存。变更 MUST 在合成边界样例、标注数据集和现场
代表性数据上执行可重复回归，并分别报告精度、稳定性、失败率和运行耗时。

### V. 模块化与集成可控
数据接入、预处理、槽特征提取、姿态估计、质量评估和输出适配 MUST 通过清晰接口解耦，允许
离线回放和独立测试。外部契约的变更 MUST 版本化并提供兼容或迁移说明。首版 MUST 选择满足
验收目标的最简单方案，新增模型、硬件依赖或并发复杂度时 MUST 说明必要性和验证方式。

## 工程约束

- 传感器、开发语言、运行平台和算法路线 MUST 在调研与计划阶段依据现场条件确定。
- 时间同步、标定、坐标变换和单位转换 MUST 有独立测试，不得散落为未命名常量。
- 性能目标 MUST 同时包含精度、延迟、吞吐、稳定性和资源占用，并写明测试环境。
- 大体积数据不直接纳入源码仓库时，MUST 提供数据清单、校验和及受控存储位置。
- 密钥、凭据、现场地址和未脱敏生产数据不得提交到 Git；日志 MUST 支持问题定位且保护数据。

## 开发流程与质量门禁

开发 MUST 依次经过 constitution、specify、必要时 clarify、plan、tasks、analyze 和 implement。
进入实现前，规格 MUST 定义坐标/姿态契约和可量化验收目标，计划 MUST 说明数据流、标定、算法
候选、接口和测试策略，任务 MUST 覆盖实现、测试、数据、文档与集成。合并前 MUST 通过单元测试、
契约测试、离线数据回归和性能基准；任何门禁豁免 MUST 记录理由、风险和补偿措施。

## Governance

本 Constitution 优先于项目内其他开发约定。修改原则或质量门禁 MUST 通过独立评审，在本文
顶部更新影响报告，并按语义化版本管理：不兼容的原则变更升主版本，新增或实质扩展原则升次版本，
不改变语义的澄清升修订版本。每个功能规格和代码评审 MUST 检查 Constitution 合规性；发现冲突时
MUST 先修订规格、计划或 Constitution，再继续实现。

**Version**: 3.0.0 | **Ratified**: 2026-08-13 | **Last Amended**: 2026-08-16
