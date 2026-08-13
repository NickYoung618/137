# Implementation Plan: 槽姿态数据无关工程基础

## Technical Context

- Python 3.12、Pillow 12.2.0，通过uv锁定。
- 当前只定义离线数据和输出契约，不实现真实姿态估计或PLC写入。
- 后续算法可复用A端面的中心定位、极坐标相关和外槽检测，但必须以扫角真值重新验证。

## Structure

- `tools/`：Manifest、数据校验和重复性评估。
- `config/`：统一标定字段、姿态坐标约定和重复性档位。
- `algorithms/slot_pose/`：fail-closed最小执行骨架。
- `contracts/`：JSON Schema和业务不变量。
- `data/`、`tests/`：目录规范与自动化测试。

## Quality Gates

1. 20张现有A端面图全哈希验证通过。
2. JSON Schema和Python语法有效。
3. 全部unittest通过。
4. 骨架对真实参考图返回明确未实现状态且角度为null。
5. 工作树不包含原始图片、虚拟环境或运行输出。
