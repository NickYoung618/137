# Research: A2 多组静态重复性与过渡盲测治理

## R1 统一路径基准

**Decision**: 使用一个显式`data-root`与相对该根的canonical inventory；物化只遍历清单行，不递归发现normal/bad。

**Rationale**: A2根下直接包含500张normal且`坏/`包含200张bad，双root递归会产生路径基准冲突和潜在重复。

**Alternatives considered**: 修改Mac主清单为两个class-root路径会丢失统一全局身份；保留双root并临时剥前缀不可审计。

## R2 空清单与显式分组

**Decision**: inventory draft允许sample/condition/repeat为空；confirmed grouping严格要求全覆盖、非空和provenance。任何空值都拒绝物化显式分组。

**Rationale**: 008的`build_manifest`会对空字段回退目录推断并自动生成repeat，可能把未知变成权威分组。

**Alternatives considered**: 继续使用单CSV并靠调用者约定风险过高。

## R3 静态重复性统计

**Decision**: 单组角度以圆均值为中心，输出最小环形覆盖极差、样本标准差和P95绝对环形残差；跨组池化组内残差并同时报告最差组。

**Rationale**: 不同工况的当前角不同，原始角度跨组极差没有重复性意义；普通线性统计在±180°附近错误。

**Alternatives considered**: 对每帧人工真值残差是accuracy评价，本批没有逐图真值；只报极差不足以描述分布。

## R4 资格与有效率

**Decision**: 采集资格要求至少20张，失败帧保留在有效率分母；有效角少于2时角度分布为不可用，但组本身仍记录为采集合格/算法结果不完整。

**Rationale**: 删除失败会虚增稳定性；将检测失败等同于采集组不合格会掩盖算法问题。

**Alternatives considered**: 要求20张全部检测有效会把检测率问题从报告中消失。

## R5 bad组权威性

**Decision**: bad每帧必须有badReason、poseUsable及非算法authority/provenance才进入权威静态组；否则保留为`BAD_SEMANTICS_UNCONFIRMED`。

**Rationale**: bad目录不等于姿态不可测或物理坏件，已有59%只能是条件指标。

## R6 过渡盲测选择

**Decision**: 候选限定为完整物理sample且没有泄漏；使用`sha256("a2-transitional-blind-v1\0" + sorted(source hashes))`的最小排序键选择，冻结整个sample。

**Rationale**: 规则确定、与算法表现无关、输入乱序不影响、可在Mac复算。

**Alternatives considered**: 随机选择需要种子与随机库状态；按编号首/末选择容易受人为排列影响；按结果质量选择构成泄漏。

## R7 严格性声明

**Decision**: 当前700锁固定为`NON_STRICT_TRANSITIONAL`、`priorExposure=true`、`maxExecutionCount=1`。

**Rationale**: 数据已查看，事后冻结只能防止未来继续查看，不能消除历史暴露。

## R8 性能与依赖

**Decision**: 清单/JSONL统计使用流式标准库，700条目标5秒内且不读图；哈希验证单独显式开启。

**Rationale**: 评估工具不应重复核心算法或引入重依赖。
