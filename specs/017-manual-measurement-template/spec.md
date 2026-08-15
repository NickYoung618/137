# Feature Specification: 唯一人工参考的注册与测量

**Feature Branch**: `main`

**Created**: 2026-08-15
**Status**: Implemented and verified

## Scope

孔2端面运行时只允许一套权威参考：人工标注JSON `018e3449...`与配对新BMP
`faf357c2...`。这张新BMP同时是全局注册的图像参考；新JSON定义Phi12.2可见弧和尺寸7的
物理边界语义。已退役资产`cc192...`/`da223...`不得作为图像、坐标系、特征库、测量先验或
任何运行时输入。

## Authoritative reference

- annotation SHA-256: `018e3449c051c15f7946315bd0d7f21cd79f4d4983efca0d11c7d98f02bfffa6`
- image SHA-256: `faf357c2e6e8e58d667f76a3d9ed4f4d51ab4d451c2661cf0efbc641405b2d8b`
- shapes: `Phi12.2` `linestrip` 80点，`7` `line` 2点
- 资产始终Git外置。

## Clarifications

1. 用户最终指令覆盖早先的“旧参考仅作注册”方案；旧资产现在完全退役。
2. 现拍端面工位中相机/零件方向固定；直接新参考注册只估计平移、尺度和小角度，
   不允许重复圆形结构用90°/180°/270°假匹配取代同向候选。
3. 同图self-check必须显式输出单位变换；它是管线自检，不是泛化证据。
4. 每张目标图仍需重新搜索Phi弧边和D7两边界；参考点不得直接冒充目标边缘。

## Requirements

- **FR-001**: 检测入口MUST只接收`reference_annotation`/`reference_image`/`target_image`/`configuration`。
- **FR-002**: 参考JSON/BMP的SHA和shape结构MUST严格校验；缺失、篡改或传入退役资产MUST明确失败。
- **FR-003**: 全局注册MUST从权威新BMP像素中提取分布式梯度/纹理支撑，不得读取退役文件。
- **FR-004**: 候选必须保留支持数、覆盖、残差、尺度和小角度原质量门，并记录图像一致性证据。
- **FR-005**: Phi角域/相位/圆先验与D7初始几何MUST只来自权威新JSON/BMP。
- **FR-006**: 每张目标必须重新检边并通过现有质量门；不降门、不做标称/固定像素补偿。
- **FR-007**: `runtimeInputs`、Schema、CLI、batch、shell和报告MUST只暴露唯一参考角色并保存SHA。
- **FR-008**: 结果MUST输出`authoritativeReference`、参考到目标变换、`templateSelfCheck`和注册证据来源。
- **FR-009**: 保持016的原始边缘证据/拟合几何/尺寸标注分层及独立证据审核状态。
- **FR-010**: 不读holdout调参，不提交BMP、人工JSON、JSONL或运行输出。

## Acceptance

- 真实self-check：注册单位变换，D7长度误差≤2 px，Phi直径误差≤1 px；明确标注为非独立泛化证据。
- 服务器9帧外置诊断集无执行错误，逐帧显式报告注册/D7/Phi状态。
- 全套unittest、compileall、Schema、SpecKit analyze、diff/大文件审计通过。
