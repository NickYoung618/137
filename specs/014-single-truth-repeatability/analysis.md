# SpecKit Analyze: 单一真值与无标注重复性诊断

**Status**: Complete; implementation and all local gates passed

## Analyze checklist

- spec的证据边界是否由输出字段和测试共同保证。
- manifest是否是唯一采集组来源，缺失和重复是否失败。
- normal/defective以及development/fixed/holdout是否没有混组统计。
- 真值FAIL是否保持FAIL，无标注统计是否只标记diagnostic。
- 运行时算法、配置、Schema和质量门是否零修改。
- 原图、LabelMe、JSONL、manifest和运行报告是否全部位于Git外。

## Requirement reconciliation

- FR-001–008、FR-010由`analyze_hole2_single_truth_study.py`及四项新测试覆盖。工具只读取已有
  JSONL、显式manifest和单图验收报告，不读取图片或LabelMe。
- FR-009以先红后绿测试证明：相邻失败帧位于不同显式组时生成两个失败段。
- cohort键固定为`population/role`；capture group键包含population，因此normal和defective即使
  captureGroupId同名也不会混合。
- `staticRepeatability`默认要求20个有效帧，输出mean、样本标准差、6σ、range和MAD。无门限，
  只有`EVALUATED/INCOMPLETE`，没有PASS/FAIL。
- 唯一真值锚点状态独立保存；测试冻结FAIL不能被无标注cohort覆盖。

## Server evidence

- 唯一真值：PASS；尺寸7误差`0.7173203881 px`，Phi直径误差`0.1053051052 px`。
- 外置非盲结果：normal development 12、diagnostic 6、fixed control 3，defective observation 8；
  execution errors均为0，分组统计未混合。
- 所有稀疏采集组均未达到20个有效帧，正确报告`INCOMPLETE`。normal-0068的两帧探索range很小，
  只说明两帧稳定；normal-0032的Phi两帧range约`40.68 px`，仅标记为优先诊断线索。
- holdout 10帧未输入本次工具，仍封存。

## Safety conclusion

本增量不改变任何测量值、有效状态或运行时门限，不产生伪真值、mm或生产OK/NG。最终静态与
大文件门已通过，可以提交。

## Verification

- 定向测试：8项通过。
- 默认依赖全套：135项通过，9项既有显式Schema用例按设计skip。
- 显式`jsonschema`全套：135项全部通过，0 skip。
- `compileall -q algorithms tools tests`：通过。
- `git diff --check`：通过。
- 大文件审计：新增/修改的Git候选均为小型源码、测试和Markdown；外置manifest、JSONL、图片、
  真值和研究报告未进入工作树。
- 运行时零改动：`algorithms/hole_2/current_capture.py`、`config/`、`schemas/`无diff。
