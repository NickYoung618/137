<!--
Sync Impact Report
- Version change: 2.0.0 -> 2.0.1
- Clarified principle IV: localization validity and measurement completeness are independent
- Required preservation: every core-invalid feature remains invalid and traceable
- No principle removed
-->
# 137 壳体 A 端面算法 Constitution

## Core Principles

### I. 规格先行与需求追踪
每项实现 MUST 关联功能规格、验收场景和任务编号。输入、输出、单位或判定语义存在歧义时，
MUST 先在规格中记录边界，不得用代码默认值替代业务确认。规格、方案、任务、测试和结果之间
MUST 可追踪。

### II. 检测核心原样复用
桌面算法包中的 A 端面核心是本仓库的权威检测实现。集成 MUST 保持该核心字节不变并记录
SHA-256；新增代码只能位于调用、契约、错误处理和测试边界。任何检测逻辑修改 MUST 作为独立、
明确授权的核心升级处理，不得混入接口重构。

### III. 输入输出可复现
每次结果 MUST 记录输入路径与指纹、标注和参考图指纹、核心版本、量测值、质量字段和配准方法。
JSON MUST 使用版本化契约和标准有限数值；不可表示的数值 MUST 写为 `null`。未经确认的物理标定
不得产生物理尺寸或正式 OK/NG。

### IV. 安全失败与边界验证
输入缺失、标注无效、参考图不可解析或检测异常时，系统 MUST 返回结构化失败，不得伪造量测值。
核心返回的无效质量字段 MUST 在逐特征质量和测量完整性中保持无效，不得被适配层改写。端面定位
有效性 MUST 与特征测量完整性独立表达；只有受控策略明确列为定位必要项的特征才可否决定位。
测试 MUST 覆盖成功、失败、非有限数值、CLI 输出和来源指纹。

### V. 数据最小化
原始图像、参考图、大型 LabelMe 标注、压缩包和运行输出 MUST 留在 Git 之外。仓库只保存代码、
规格、契约、小体积配置与测试夹具。需要跨机器复现时，使用相对路径 Manifest 和 SHA-256，
不得复制大文件进源码历史。

## 工程约束

- 仓库范围只包含 A 端面检测，不包含姿态引导或设备写入业务。
- Python 与依赖版本 MUST 锁定；CLI MUST 可在无服务进程的环境下独立执行。
- 标注中的参考图路径 MUST 显式解析并参与结果追溯。
- 对外 JSON 变更 MUST 版本化并通过契约测试。
- 密钥、凭据、现场地址和未脱敏生产数据不得提交 Git。

## 开发流程与质量门禁

开发依次经过 specify、plan、tasks 和 implement。合并前 MUST 通过单元测试、CLI 契约测试、
桌面来源指纹检查、外置参考资产冒烟和大文件审计。无法执行的门禁 MUST 如实记录原因，
不得用合成成功替代真实资产验证。

## Governance

本 Constitution 优先于项目内其他开发约定。修改原则或质量门禁 MUST 更新顶部影响报告并按
语义化版本管理。每个规格和代码评审 MUST 检查合规性；发现冲突时先修订规格或方案再实现。

**Version**: 2.0.1 | **Ratified**: 2026-08-13 | **Last Amended**: 2026-08-13
