# Implementation Plan: 孔2数据无关工程基础

## Technical Context

- Python 3.12、NumPy 2.4.4、Pillow 12.2.0，通过uv锁定。
- 原图位于外置目录；仓库只保存清单、配置、代码和小体积报告。
- 算法输入保持现有LabelMe参考模型和目录扫描方式。

## Structure

- `tools/`：Manifest、数据校验和重复性评估。
- `config/`：标定、映射、公差及重复性档位模板。
- `algorithms/hole_2/`：有来源指纹的算法适配。
- `data/`：目录规范和可提交Manifest位置。
- `tests/`：数据工具与适配层单元测试。

## Quality Gates

1. JSON和Python语法校验。
2. 全部unittest通过。
3. 参考图实际运行成功。
4. `mm_per_px=null`时报告单位为px且档位不判定。
5. 工作树不包含原始图片、虚拟环境或运行输出。
