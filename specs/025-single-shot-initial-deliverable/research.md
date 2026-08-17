# Research: 单拍槽姿态初版

## Decision 1: 初版以单拍为唯一成功路径

- **Decision**: 单张图像独立完成外圆、真槽、双壁、槽口和引导角计算。
- **Rationale**: 现场暂无同件180°配对图，用假配对无法证明双拍有效性。
- **Alternatives considered**: 等待双拍数据；被拒，会阻塞可独立完成的单拍初版。

## Decision 2: 遮挡时不恢复不可见槽壁

- **Decision**: 任一槽壁不可见、与fixture边混合或存在多解时fail-closed。
- **Rationale**: 单帧中不可见的线没有可验证像素证据，补造会把稳定假阳性变成旋转指令。
- **Alternatives considered**: 用标准槽宽对称补齐；被拒，只能作非权威诊断，不得产生引导角。

## Decision 3: 复用已有圆与槽几何链

- **Decision**: 沿用已审计并已内联到本仓库的gyj/yyh A端面外缘射线、robust circle fit、polar/profile基础能力，以及现有亚像素槽壁精修。
- **Rationale**: 145独立长弧真值已证明候选几何角误差0.013368°；当前核心问题是检测接受/拒绝与局部根因，不是重写整套拟圆。
- **Alternatives considered**: 新建Hough/生成式/训练模型；被拒，无真值支持且增加集成风险。

## Decision 4: 二级同源性裁决仅处理已证实的contrast-only误拒

- **Decision**: 保留原0.12对比度失败证据，只有原失败集精确为`edge_contrast_asymmetry`且端点/剖面/深度等非contrast证据全过时才可裁决。
- **Rationale**: 145/147已人工确认两壁完整同源；374混边的端点结构差能保持拒绝。
- **Alternatives considered**: 把0.12改成0.19；被拒，会丢失原门证据并扩大未知假阳性。

## Decision 5: 错误分层是初版功能，不是调试附属品

- **Decision**: 圆候选、物理圆、真槽识别、歧义、槽壁精修、部分观测和混边保留不同错误码/阶段。
- **Rationale**: 现场需要知道“为什么没角度”，否则无法区分算法问题、遮挡和采集质量问题。
- **Alternatives considered**: 所有失败统一`DETECTION_FAILED`；被拒，无法根因闭环。

## Decision 6: 用现有双壁精修解除有界粗候选歧义

- **Decision**: 025剖面对最多3个粗门候选逐个运行既有亚像素双壁、外圆交点、同源性和二级裁决，仅唯一完整通过时选中。
- **Rationale**: 261中人工确认的真槽candidate-004形成完整两壁，阴影candidate-006两侧均不足；281阴影也无法形成双壁。374混合边虽能形成两条直线，仍被未放宽的同源性/端点证据拒绝。因此“逐个执行完整物理链”能解决261，同时保留已知负例。
- **Alternatives considered**: 按grooveScore最高、candidate编号或固定角度选取；全部拒绝，前者会把阴影分数当身份，后两者把人工语义泄漏到运行时。

## Decision 7: 当前不修改外圆残差门

- **Decision**: 为141/161/441保留失败，并新增Git外逐射线边族追踪。
- **Rationale**: 三图均存在主边族和集中在约22°–42°、318°–338°的向内切换族，但当前鲁棒拟合已经剔除大部分远离点，141/161仍在残差门附近失败，尚不能证明应放宽残差或排除固定扇区。
- **Alternatives considered**: 固定屏蔽阴影角区或直接提高P95门；拒绝，真实槽可旋转到这些角度，且目前没有141/161/441独立外圆像素真值。
