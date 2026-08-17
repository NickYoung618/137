# Implementation Plan: 单拍槽姿态初版交付

**Branch**: `025-single-shot-initial-deliverable` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

## Summary

在已有`single_real_groove`、亚像素槽壁精修、同源性裁决和单张引导公式上收敛一个单拍初版剖面。初版剖面显式开启已有且经145/147正例、374反例验证的二级同源性裁决，保留原0.12对比度门证据；输出图像引导但始终阻断PLC。未确认代表图只增强证据和错误定位，不调门限。

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: 标准库、NumPy、Pillow，仓库内`algorithms.end_face.core`

**Storage**: JSON/JSONL/CSV输出；BMP/JPEG和人工标注留Git外

**Testing**: `unittest`、Draft 2020-12 JSON Schema、Git外小样本回放

**Target Platform**: Linux服务器与macOS离线验证

**Project Type**: 离线CLI+可嵌入算法库

**Performance Goals**: 同机单图P95不高于2.5秒，新增纯标量裁决不重复解码或拟圆

**Constraints**: 单拍、单帧可部署、fail-closed、不读人工真值、不依赖yyh/gyj绝对代码路径、不读sealed part-006、PLC null

**Scale/Scope**: 先用9张代表图和按物理零件分组的小样本；不用700张循环调参

## Constitution Check

- I 规格先行：PASS，025将单拍与遮挡失败写成可测FR/SC。
- II 坐标契约：PASS，沿用`image-y-down-clockwise-signed/1`和85°±5°。
- III 安全失败：PASS，单壁、混边、歧义和圆失败均无角度。
- IV 数据溯源：PASS，真实数据按SHA留Git外，按物理零件分组。
- V 模块与集成：PASS，复用仓内唯一A端面核心，不修改PLC。

## Project Structure

```text
algorithms/slot_pose/              # 已有单槽检测、精修、同源性和引导
tools/                             # 初版配置物化、单图/小样本回放和诊断
contracts/                         # 配置及输出Schema
tests/                             # 契约、环形角、fail-closed、正反例测试
specs/025-single-shot-initial-deliverable/
```

**Structure Decision**: 不建第二套检测器；025通过一个版本化单拍剖面组合已有检测阶段，仅对有独立证据的缺口修改代码。

## Delivery Phases

1. 固化单拍请求/结果语义和初版配置剖面，保证PLC始终为null。
2. 证明145/147可输出引导且374继续拒绝，不改原同源性门。
3. 对141/161/441/281/261/401保留分阶段诊断；仅在人工语义确认后逐类进入TDD修复。
4. 运行小样本、独立物理零件回归、全量测试、Schema、性能与污染门。
5. 对141/161/441输出逐射线边族证据；对261/281/374逐候选运行相同亚像素双壁诊断。仅将已有、有界且跨正反例成立的多候选精修消歧纳入025剖面，不修改圆残差或槽识别门限。
