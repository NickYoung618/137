# Feature Specification: 槽姿态数据无关工程基础

**Feature Branch**: `main`
**Created**: 2026-08-13
**Status**: Implemented baseline

## User Scenarios & Acceptance

### 外置A端面数据可验证

服务器和Mac可使用相同Manifest验证外置A端面图片，缺图、哈希变化、分组错误必须明确失败。

### 姿态重复性可离线计算

真实算法输出带符号角度CSV后，可按固定角度组计算静态重复性，并按各位置/角度组均值计算动态
重复性。角度限值未确认时只输出统计量，不产生PASS/FAIL。

### 未实现算法安全失败

在真实槽姿态算法接入前，最小骨架能读取图像、绑定图像和配置指纹并输出合法JSON契约，
但必须返回`not_implemented`、`valid=false`和`angle=null`。

## Requirements

- **FR-001**: 原始图片必须外置，Manifest必须可跨Mac和服务器复用。
- **FR-002**: 数据验证必须默认校验SHA-256、图像属性及每组期望张数。
- **FR-003**: 重复性统计必须区分固定位置静态统计与位置均值动态统计。
- **FR-004**: 配置必须保留`mm_per_px`并表达姿态坐标、方向、零位、特征映射和档位。
- **FR-005**: 输出必须包含任务、图像、算法/配置版本、带符号角度、置信度、有效性和错误。
- **FR-006**: 无效结果不得携带角度；有效结果必须携带数值角度和置信度。
- **FR-007**: Production PLC映射未确认前不得编码或写入具体PLC地址。
- **FR-008**: 姿态技术有效性不得解释为质量OK/NG。

## Success Criteria

- **SC-001**: 现有20张A端面数据通过全哈希Manifest验证。
- **SC-002**: 单元测试覆盖Manifest、重复性和输出契约不变量。
- **SC-003**: 5472×3648参考图可生成fail-closed契约且不返回虚假零角度。
