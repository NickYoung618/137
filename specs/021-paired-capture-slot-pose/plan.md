# Implementation Plan: 双帧配对槽姿态与可复核预标注

**Branch**: 021-paired-capture-slot-pose | **Date**: 2026-08-16 | **Spec**: spec.md

## Summary

在020单帧圆定位、暗区、真槽几何、亚像素侧壁和同源性诊断之上增加独立、默认关闭的双帧编排层。140张真实BMP trace曾证明原粗暗区只向内搜索会漏掉区间外墙证据；随后part-019 374人工线确认285.953°既有cluster是一条可见真实槽壁，但并未证明相对侧壁在该帧可见。双向搜索因此只负责枚举实际可观测墙，不负责恢复被遮挡像素；只有完整同源两壁可见时才评估无序canonical wall pair，单壁观测继续fail-closed。双拍仍负责保证至少一拍无遮挡。该路径不改变020权威状态或姿态。

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: 标准库、NumPy、Pillow、现有slot_pose/gyj适配；不新增生产依赖
**Storage**: Git内Schema、配置示例、脱敏文档；BMP、LabelMe、叠加图和运行结果全部Git外
**Testing**: unittest、jsonschema、纯数学合成候选、临时图像/JSON CLI测试
**Target Platform**: Linux服务器开发；macOS原始BMP离线回放；单进程CPU
**Project Type**: Python算法库与离线CLI
**Performance Goals**: 双帧匹配本身P95小于20ms/对（不含两个单帧检测）；双向局部搜索有严格的domain/seed/wall上限，不复制全分辨率图像；默认关闭的历史耗时门不回退
**Constraints**: fail-closed、参数配置化、固定角不屏蔽、part-006封存、默认关闭、不合main
**Scale/Scope**: 双向局部墙搜索与双拍契约的合成验证；Git外140张单帧BMP分折回放；part-019 374/369简化审阅；part-008 145/147干净槽壁语义及独立像素复核；墙/端点残差离线诊断与默认关闭的同源门实验候选；真实双拍数据尚未到位

## Constitution Check

- 规格先行：PASS。104项FR和44项SC覆盖契约、未知参数、安全失败、审阅语义、双向墙候选、无序墙对、逐seed可追溯性、部分观测状态、完整槽人工复核、独立像素残差和默认关闭同源候选。
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
10. `local_second_wall.py`在实验开关开启且020因同源性失败时运行；原start/end只定义待验证anchor。对start/end分别建立inward/outward搜索域，inward最多到原区间中点，outward最多到物理槽宽上限，全部角度wrap360。
11. 每个搜索域对falling/rising极性独立播种，复用既有亚像素径向梯度、共识直线和外圆交点。接受拟合按极性和角度聚成physical wall cluster，cluster保留所有domain/seed来源。
12. 枚举一falling与一rising cluster的无序墙对，canonical ID仅由排序后cluster ID决定。依次检查物理槽宽、直壁/平行、径向深度与覆盖、外圆端点、暗开口连续性、槽肩/端点与同源剖面。与原已拒绝start/end相同的墙对显式拒绝，避免复现混合边。
13. 唯一实验解只写入`diagnostics.localSecondWallDiagnostic`，标记不可提升；顶层失败码、valid、姿态和PLC字段完全不变。
14. diagnostic/3保留search domain、每个seed的生成/拒绝、physical wall cluster、canonical pair和分层failedChecks；Git外提取工具只读JSONL，不读取原图。
15. 审阅工具只画cluster代表与最终canonical pair，标注`AUTO_experimental_`、`human_verified=false`和不权威声明，不画每个raw seed。
16. 人工审核shape先核对几何而非相信label字面；原件和SHA不变，派生副本只把374的已确认线语义规范为可见真实槽壁，并显式声明它不是相对侧壁真值。
17. 若仅一条真槽壁可观测，局部诊断保留墙证据和失败原因但不计算完整槽中点；当前顶层继续fail-closed。双拍中必须由至少一张无遮挡帧提供完整开口。
18. `local-second-wall-diagnostic/4`将“有墙状证据但无完整同源槽口”表达为`PARTIALLY_OBSERVED`；它不选择真壁身份、不读取人工标签，外层错误和所有引导字段保持失败/null。
19. `build_complete_groove_review_queue.py`只读合并冻结manifest和JSONL，按sample对账双壁证据；已知partial sample通过显式审计排除项剔除，候选sample内只用身份SHA稳定抽帧。

20. part-008 145/147的最终A语义写入独立证据：AUTO槽壁正确干净，非槽候选标记与fixture shadow关联且区域不完整。旧污染子段工具保留参数兼容但在任何写出前稳定拒绝；历史产物仅供审计。最小像素复核改为人工独立墙支持点与槽口端点，不画fixture overlap。
21. `prepare_clean_groove_pixel_review.py prepare`只核对review-index、raw与AUTO文件SHA；AUTO文件不解析shape。它为显式imageId生成`shapes=[]`、`imageData=null`的Git外LabelMe任务，人工在原始图像上独立落点。
22. 同一工具的`validate`子命令只读人工完成LabelMe：强制每墙至少3个独立point、左右端点各1个point，并把可选的独立外圆可见弧/圆心与墙端点完成状态分开报告。报告永远保持accuracy/tuning/runtime/PLC权限为false。
23. `compare_clean_groove_pixel_truth.py`只读正式validation、HUMAN LabelMe和runtime JSONL，并且只按image SHA唯一关联。它逐墙计算HUMAN点到AUTO墙线、AUTO支持点到HUMAN TLS线、无向墙角差，逐端点计算二维误差，并分开输出中点/槽宽误差。
24. 当独立外圆参考缺失时，HUMAN/AUTO中点方向都使用同一个runtime物理圆心；输出明确标记为conditional，不评价外圆误差或最终姿态角精度，也不把HUMAN坐标回灌运行时。
25. `sidewall_source_consistency_candidate`是独立、默认关闭且不可升权的实验仲裁。它只消费现有source-consistency数值：原结果只失败contrast、其余原检查全通过且独立端点结构门通过时可标记`CANDIDATE_SUPPORTED`；它永不修改原status、refinement、顶层valid/角度/PLC。
26. 145/147只用于确认contrast-only误拒与像素残差；part-019已知混合边用于保护负例。实验端点门是development-only，必须输出版本和阈值，不能据一个正样品和一个负样品宣称泛化或默认启用。

## Project Structure

    specs/021-paired-capture-slot-pose/
      spec.md plan.md research.md data-model.md contracts/ quickstart.md tasks.md
    algorithms/slot_pose/paired_capture.py
    algorithms/slot_pose/local_second_wall.py
    tools/run_paired_slot_pose.py
    tools/prepare_slot_pose_prefill_review.py
    tools/extract_local_second_wall_trace.py
    tools/build_complete_groove_review_queue.py
    tools/prepare_fixture_contamination_annotation.py
    tools/prepare_clean_groove_pixel_review.py
    tools/compare_clean_groove_pixel_truth.py
    contracts/paired-capture-manifest.schema.json
    contracts/paired-slot-pose-config.schema.json
    contracts/paired-slot-pose-result.schema.json
    contracts/local-second-wall-diagnostic-config.schema.json
    contracts/local-second-wall-diagnostic-result.schema.json
    contracts/complete-groove-review-queue.schema.json
    contracts/fixture-contamination-review.schema.json
    contracts/clean-groove-pixel-review.schema.json
    contracts/clean-groove-residual-diagnostic.schema.json
    contracts/sidewall-source-consistency-candidate-config.schema.json
    config/paired-capture-slot-pose.example.json
    config/local-second-wall-diagnostic.example.json
    tests/test_paired_capture_slot_pose.py
    tests/test_slot_pose_prefill_review.py
    tests/test_local_second_wall.py
    tests/test_local_second_wall_trace.py
    tests/test_complete_groove_review_queue.py
    tests/test_fixture_contamination_annotation.py
    tests/test_clean_groove_pixel_review.py
    tests/test_clean_groove_residual_diagnostic.py
    tests/test_sidewall_source_consistency_candidate.py

**Structure Decision**: 双拍功能不进入legacy_adapter选择链；局部第二壁模块只通过legacy_adapter的诊断钩子运行且禁止改变选择结果。图像审阅独立于生产算法。

## Phase 0 Research Decisions

- 旋转公式采用第二帧减有符号机械旋转映射回第一帧；方向和单位写入契约，不使用隐式常量。
- UNCONFIRMED是合法采集状态而不是配置错误；若数值齐全可计算诊断假设，但不能valid。
- 固定阴影在相机坐标不动、真槽随件转动是配对主证据；小旋转无法判别时拒绝。
- 匹配以角残差为主，形状/剖面用于拒绝跨源组合；不依据第三候选或固定角窗口直接选择。
- 输出以第二次拍摄后的零件姿态为current；第一帧测量必须通过已确认旋转传播，禁止复用旧角。
- 自动预标注只使用AUTO_标签和human_verified=false；人工标签由现场另行确认。简化图只展示“被复核对象”，020 fixture候选不等于020 valid，且不自动生成真值框。
- fixture模板pairEvidence是身份选择唯一来源；candidateMatches中的NOT_MATCHED只说明比较过，不允许nearest补位。raw interval始终只是一维暗区证据。
- 双向墙实验采用“搜索域→独立墙→无序墙对→枚举并保留失败”的诊断架构；原暗区不是硬边界，但物理槽宽和总seed上限仍是硬约束。不修改020 source consistency阈值，也不把唯一实验解升级为姿态。
- `PARTIALLY_OBSERVED`描述观测充分性而不描述物理身份：一个或多个墙状cluster存在、但完整同源墙对不成立时可输出；人工确认只在外置审核记录中绑定候选，运行时字段明确`humanConfirmationAppliedAtRuntime=false`。
- 完整槽人工复核队列以物理sample为选择单元；算法阶段只用于找“值得人工看”的组，不用于test拆分、阈值选择或准确率声明。组内选帧完全由SHA身份散列决定。
- 完整槽身份确认与像素线真值分开：145/147的A语义确认AUTO槽壁正确干净，但这仍不是独立亚像素坐标。下一步只标每壁分散支持点和两槽口端点，不画fixture overlap；姿态角精度最终还需独立外圆真值。
- 独立像素任务从空`shapes`开始：AUTO LabelMe仅通过SHA验证来源，工具不解析其几何。完成校验允许先完成墙/端点，再单独补外圆弧或圆心；这两个阶段的可用状态不能互相冒充。

## Phase 1 Design Outputs

- data-model.md：manifest、旋转契约、候选、匹配假设、结果状态、审阅包。
- contracts/paired-capture.md：输入、配置和输出行为契约。
- quickstart.md：服务器测试、Mac配对运行与374/369审阅命令。
- clean-groove-pixel-review.schema.json：空白任务、人工完成状态、独立外圆参考与永久禁止升权策略。
- clean-groove-residual-diagnostic.schema.json：按SHA关联的墙/端点/条件方向残差与永久禁止升权策略。
- sidewall-source-consistency-candidate-config.schema.json：默认关闭的development-only替代判据配置。

## Post-Design Constitution Re-check

PASS WITH BLOCKERS。设计没有猜现场参数、没有改变默认单帧路径，也不产生PLC命令。服务器140张BMP可证明候选生成结构与fail-closed；374人工线只确认一条可见真壁。145/147已确认真实完整槽身份、干净槽壁和槽肩端点语义，并完成3+3墙点和2端点的独立像素复核；非槽fixture阴影标记不完整是独立缺口。墙/端点残差可以离线评价，但无独立外圆/圆心，最终姿态角精度仍不可评价。真实双拍BMP、确认旋转参数、独立外圆真值及更多物理零件正负真值仍是生产验收阻塞。

## Complexity Tracking

新增一个纯匹配模块和两个CLI是为了隔离生产单帧算法、离线编排与人工复核；无并发、模型或外部服务。候选笛卡尔积有严格上限，避免数据相关的资源膨胀。
