# Implementation Plan: 双帧配对槽姿态与可复核预标注

**Branch**: 021-paired-capture-slot-pose | **Date**: 2026-08-16 | **Spec**: spec.md

## Summary

在020单帧圆定位、暗区、真槽几何、亚像素侧壁和同源性诊断之上增加独立、默认关闭的双帧编排层。每帧仍由既有算法产出完整候选；配对层只处理身份、旋转归一化、一对一匹配、唯一性、无遮挡选择和第二拍后引导。审阅层将020的一维暗区证据严格画成角度区间而非fixture区域。另增默认关闭的局部第二侧壁实验诊断：复用现有亚像素侧壁精修/同源性证据，枚举同一局部开口内的第二壁，但绝不改变020权威状态或姿态。

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: 标准库、NumPy、Pillow、现有slot_pose/gyj适配；不新增生产依赖
**Storage**: Git内Schema、配置示例、脱敏文档；BMP、LabelMe、叠加图和运行结果全部Git外
**Testing**: unittest、jsonschema、纯数学合成候选、临时图像/JSON CLI测试
**Target Platform**: Linux服务器开发；macOS原始BMP离线回放；单进程CPU
**Project Type**: Python算法库与离线CLI
**Performance Goals**: 双帧匹配本身P95小于20ms/对（不含两个单帧检测）；候选数每帧上限16；不复制全分辨率图像
**Constraints**: fail-closed、参数配置化、固定角不屏蔽、part-006封存、默认关闭、不合main
**Scale/Scope**: 单帧局部第二壁和双拍契约的合成验证；part-019 374/369 Git外预标注；真实双拍数据尚未到位

## Constitution Check

- 规格先行：PASS。42项FR和13项SC覆盖契约、未知参数、安全失败、审阅区间语义和局部第二壁诊断。
- 坐标与姿态：PASS。明确image profile、第一拍零件坐标、第二拍当前角和PLC边界。
- 质量与安全失败：PASS。缺帧、未确认参数、0/多解、残差和遮挡均有稳定状态。
- 数据溯源：PASS。sample/pair/capture/SHA齐全，原图Git外，part-006禁止读取。
- 模块化与集成：PASS。单帧检测不改，paired_capture为纯编排与数学模块，CLI分离。
- 性能：DESIGN_PASS / REAL_DATA_BLOCKED。匹配复杂度由16×16硬上限控制；真实双拍端到端耗时待Mac测。

## Architecture and Data Flow

1. paired manifest校验同sample、唯一pair、capture 1/2、SHA和旋转状态。
2. 两张图分别运行现有single_real_groove配置，保留成功或失败payload中的全部diagnostics。
3. 从rawCandidates、grooveRecognition.assessments、grooveCandidates和refinement提取统一CandidateEvidence；不提前只选一个。
4. 若旋转数值可用，令顺时针为正：`theta2InPart = wrap360(theta2Image - signedRotation)`。
5. 枚举所有跨帧一对一候选，计算环形角残差、宽度/prominence/deficit/profile差和质量证据。
6. 候选上限、残差门、形状门及best-second唯一性门依次fail-closed。31°/328°不参与否决。
7. 至少一侧为可信无遮挡候选才可测量；优先第二帧直接测量，否则用第一帧加已知旋转推导第二拍后姿态。
8. currentAngle从负Y轴顺时针有符号；target=85±5；输出图像最短修正，PLC字段永远不权威。
9. review工具读取显式图片名/manifest与019/020 JSONL，核SHA后只生成原分辨率raw、单张simplified、精简AUTO_LabelMe及RAW/SIMPLIFIED两栏联系表；fixture只展示pairEvidence选择或未确认暗区，一维start/center/end画角度括号与三刻线，不画实心区域。
10. `local_second_wall.py`在实验开关开启且020因同源性失败时运行；分别锚定已有两侧，在raw暗区局部范围内用既有侧壁采样/拟合产生备选边，并按区间、平行、覆盖、端点、暗开口及剖面门枚举所有假设。
11. 唯一实验解只写入`diagnostics.localSecondWallDiagnostic`，标记不可提升；顶层失败码、valid、姿态和PLC字段完全不变。
12. 局部诊断按candidate anchor→side search→local geometry→mouth endpoint→opening structure→sidewall source→uniqueness分层，硬物理矛盾不可被score覆盖；错误码保留失败阶段。

## Project Structure

    specs/021-paired-capture-slot-pose/
      spec.md plan.md research.md data-model.md contracts/ quickstart.md tasks.md
    algorithms/slot_pose/paired_capture.py
    algorithms/slot_pose/local_second_wall.py
    tools/run_paired_slot_pose.py
    tools/prepare_slot_pose_prefill_review.py
    contracts/paired-capture-manifest.schema.json
    contracts/paired-slot-pose-config.schema.json
    contracts/paired-slot-pose-result.schema.json
    config/paired-capture-slot-pose.example.json
    tests/test_paired_capture_slot_pose.py
    tests/test_slot_pose_prefill_review.py
    tests/test_local_second_wall.py

**Structure Decision**: 双拍功能不进入legacy_adapter选择链；局部第二壁模块只通过legacy_adapter的诊断钩子运行且禁止改变选择结果。图像审阅独立于生产算法。

## Phase 0 Research Decisions

- 旋转公式采用第二帧减有符号机械旋转映射回第一帧；方向和单位写入契约，不使用隐式常量。
- UNCONFIRMED是合法采集状态而不是配置错误；若数值齐全可计算诊断假设，但不能valid。
- 固定阴影在相机坐标不动、真槽随件转动是配对主证据；小旋转无法判别时拒绝。
- 匹配以角残差为主，形状/剖面用于拒绝跨源组合；不依据第三候选或固定角窗口直接选择。
- 输出以第二次拍摄后的零件姿态为current；第一帧测量必须通过已确认旋转传播，禁止复用旧角。
- 自动预标注只使用AUTO_标签和human_verified=false；人工标签由现场另行确认。简化图只展示“被复核对象”，020 fixture候选不等于020 valid，且不自动生成真值框。
- fixture模板pairEvidence是身份选择唯一来源；candidateMatches中的NOT_MATCHED只说明比较过，不允许nearest补位。raw interval始终只是一维暗区证据。
- 第二壁实验采用“枚举并保留失败”的诊断架构；不修改020 source consistency阈值，也不把唯一实验解升级为姿态。

## Phase 1 Design Outputs

- data-model.md：manifest、旋转契约、候选、匹配假设、结果状态、审阅包。
- contracts/paired-capture.md：输入、配置和输出行为契约。
- quickstart.md：服务器测试、Mac配对运行与374/369审阅命令。

## Post-Design Constitution Re-check

PASS WITH BLOCKERS。设计没有猜现场参数、没有改变默认单帧路径，也不产生PLC命令。真实双拍BMP、确认旋转参数、端到端性能和人工标注是现场验收阻塞，不妨碍默认关闭框架交付。

## Complexity Tracking

新增一个纯匹配模块和两个CLI是为了隔离生产单帧算法、离线编排与人工复核；无并发、模型或外部服务。候选笛卡尔积有严格上限，避免数据相关的资源膨胀。
