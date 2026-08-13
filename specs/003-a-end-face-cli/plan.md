# Implementation Plan: A 端面独立检测 CLI

## Summary

移除现有姿态引导业务，将桌面算法包的 A 端面核心按原始字节纳入独立模块，在其外增加单图 CLI、
严格 JSON 契约、来源追踪和失效处理。原始资产继续外置。

## Technical Context

- **Language/Version**: Python 3.12
- **Dependencies**: NumPy 2.4.4, Pillow 12.2.0, uv lock
- **Input**: LabelMe 标注、标注引用的参考图、目标图
- **Output**: `a-end-face-result/1` JSON
- **Testing**: Python unittest；外置权威参考资产冒烟
- **Constraints**: 核心 SHA-256 必须保持 `f408631e…f8fbc`；Git 无原图/归档/运行输出

## Constitution Check

| Gate | Plan |
| --- | --- |
| 规格先行 | FR、场景、任务和测试逐项关联 |
| 核心原样复用 | 机械复制并以 SHA-256 测试锁定 |
| 可复现输出 | 三项输入指纹、核心指纹、配准和质量字段写入 JSON |
| 安全失败 | 异常返回失败对象；非有限值写 null |
| 数据最小化 | 外置真实资产；忽略归档和 outputs |

## Project Structure

```text
algorithms/end_face/
├── core.py
├── contract.py
└── main.py
contracts/a-end-face-result.schema.json
tests/test_end_face_contract.py
tests/test_end_face_cli.py
specs/003-a-end-face-cli/
```

## Implementation Phases

1. 删除姿态引导算法、契约、工具、测试和规格。
2. 从桌面 zip 原样引入 A 端面核心并固定来源指纹。
3. 实现单图 CLI、JSON 契约、严格数值转换与失败语义。
4. 增加契约/CLI/来源测试，执行外置参考资产冒烟和大文件审计。

## Quality Gates

1. 全部 unittest 通过。
2. CLI `--help` 与文件/标准输出路径通过。
3. 严格 JSON 序列化不出现非标准数值。
4. 核心 SHA-256 与 zip 内源文件一致。
5. 外置 A 端面参考图完成实际检测。
6. Git 跟踪文件无图片、压缩包或超过 5 MiB 的业务资产。
