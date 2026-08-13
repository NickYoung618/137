# Feature Specification: A 端面独立检测 CLI

**Feature Branch**: `main`
**Created**: 2026-08-13
**Status**: Implemented

## User Scenarios & Testing

### User Story 1 - 单图端面检测（Priority: P1）

算法工程师给出一份 A 端面标注、对应参考图和一张待测图，即可独立运行检测并得到机器可读结果，
无需启动其他业务服务。

**Independent Test**: 对外置参考资产运行一张图，命令退出成功并生成符合契约的 JSON。

**Acceptance Scenarios**:

1. **Given** 标注、参考图和待测图均有效，**When** 执行单图检测，**Then** 结果包含输入指纹、
   配准方法、完整量测和质量字段。
2. **Given** 输入或参考资产不可读取，**When** 执行检测，**Then** 返回结构化失败且不伪造量测。

### User Story 2 - 严格 JSON 集成（Priority: P2）

集成方可从标准输出或指定文件读取版本化 JSON，并以稳定字段判断技术执行状态和量测有效性。

**Independent Test**: 注入有限值、非有限值和无效质量标记，输出可被严格 JSON 解析器读取。

**Acceptance Scenarios**:

1. **Given** 核心返回非有限数值，**When** 序列化结果，**Then** 相应字段为 `null`。
2. **Given** 任一特征质量无效，**When** 生成结果，**Then** `result.valid=false` 并列出特征名。
3. **Given** 使用严格模式且检测失败或结果无效，**When** 命令结束，**Then** 返回非零退出码。

### User Story 3 - 核心来源与数据边界可审计（Priority: P3）

维护者可确认检测核心来自指定桌面算法包且未被重写，同时仓库历史不包含原图、参考图或压缩包。

**Independent Test**: 校验核心 SHA-256、所需入口函数、Git 跟踪文件大小和扩展名。

## Edge Cases

- 标注文件存在但 `imagePath` 指向不存在的参考图。
- 核心返回 `NaN`、正负无穷或 NumPy 标量。
- 输出目录尚不存在。
- `pixel-size` 为零或负数。
- 多个质量字段同时无效。

## Requirements

- **FR-001**: 系统 MUST 提供只依赖文件输入的 A 端面单图命令行入口。
- **FR-002**: 系统 MUST 复用指定桌面算法包内的 A 端面检测核心，不得重写检测逻辑。
- **FR-003**: 系统 MUST 记录并校验复用核心的 SHA-256 来源指纹。
- **FR-004**: 输出 MUST 是版本化、严格可解析的 JSON，可写标准输出或指定文件。
- **FR-005**: 成功输出 MUST 包含输入/标注/参考图指纹、算法指纹、配准方法、量测和有效性。
- **FR-006**: 检测异常 MUST 输出失败状态、稳定错误代码和消息，不得携带伪造量测。
- **FR-007**: 非有限数值 MUST 转换为 `null`，不得输出非标准 JSON 数值。
- **FR-008**: 核心质量无效标记 MUST 汇总为无效特征，并使总体量测有效性为假。
- **FR-009**: 原图、参考图、大型标注、压缩包和运行输出 MUST 不进入 Git。
- **FR-010**: 仓库 MUST 不包含与 A 端面检测无关的姿态引导业务。
- **FR-011**: 未确认物理标定时 MUST 保持像素单位，不得给出正式质量 OK/NG。

## Key Entities

- **Inspection Input**: 待测图、标注、由标注解析的参考图、像素比例和任务标识。
- **Core Provenance**: 核心名称、版本和源文件 SHA-256。
- **Inspection Result**: 执行状态、总体有效性、无效特征、配准方法和量测映射。
- **Inspection Error**: 稳定错误代码和可诊断消息。

## Assumptions

- 标注沿用桌面核心支持的 LabelMe 格式，并通过 `imagePath` 引用参考图。
- 默认像素比例为 1，仅表达像素量。
- 本功能不定义质量公差、生产 OK/NG 或设备写入。

## Success Criteria

- **SC-001**: 一条命令可在 30 秒内处理权威参考图并生成可解析 JSON。
- **SC-002**: 100% 契约测试通过，且输出中不出现 `NaN` 或 `Infinity`。
- **SC-003**: 仓库内核心 SHA-256 与桌面包源文件完全一致。
- **SC-004**: Git 跟踪文件中不存在原图、归档文件或超过 5 MiB 的业务资产。
- **SC-005**: 代码、文档和测试中不再提供姿态引导入口或契约。
