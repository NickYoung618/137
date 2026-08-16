# Research: 固定阴影与双侧壁同源性

## Decision 1: 固定角只作nuisance prior

**Decision**: 31°和328°只参与模板位置匹配，原始候选始终保留。
**Rationale**: 真槽可转到任意位置，part-015/021显示槽与阴影会合并。
**Alternatives considered**: 固定角屏蔽、删除两个候选后取剩余候选；两者都会漏检或误配，拒绝。

## Decision 2: 模板采用多证据硬门

**Decision**: 位置、宽度、显著度、亏损、灰度剖面、梯度剖面分别输出；两阴影还需成对相似。
**Rationale**: 当前302帧支持固定位置和较小亏损，但单个统计量不能证明物理来源。
**Alternatives considered**: 只按deficitArea或综合score；会过拟合当前零件，拒绝。

## Decision 3: 侧壁剖面统一方向

**Decision**: start和end侧都转换为“金属到暗区”的局部灰度剖面，保留原始灰度、标准化灰度、梯度和径向位置。
**Rationale**: 两侧物理极性相反，直接比较原始左右方向会把同一槽误判为不同。
**Alternatives considered**: 只比较edgeContrastMedian；part-019说明单值不足以表达局部来源。

## Decision 4: 同源性采用不可互相抵消的门

**Decision**: 对比归一化差、剖面MAE/相关、梯度差、径向支持、端点灰度结构分别有硬门。
**Rationale**: 错误混合边可同时拥有强梯度和低直线残差；加权平均会隐藏关键失败。
**Alternatives considered**: 单一grooveScore；拒绝。

## Decision 5: 重叠分解必须有参考剖面

**Decision**: 只有模板含已人工复核的固定长度参考剖面时才允许生成残差候选；否则状态为diagnostic_incomplete。
**Rationale**: 历史JSON没有局部剖面，凭角度和亏损重建阴影会把假设当事实。
**Alternatives considered**: 用302帧统计均值直接生成生产模板；没有图像级标签，拒绝。

## Decision 6: 019/020暂不合入main

**Decision**: 功能分支可推送，默认保持关闭；等待Mac原始BMP和人工标签通过后再讨论合并。
**Rationale**: part-019已证明稳定输出可能稳定地错。
**Alternatives considered**: 以20/20稳定作为发布门；拒绝。
