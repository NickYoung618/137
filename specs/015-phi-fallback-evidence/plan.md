# Implementation Plan: Phi回退证据与累计圆心边界

1. [完成] 测试先行：低/高phase保留率、累计圆心越界、强phase允许、控制门限冻结。
2. [完成] 在phase诊断中增加inlier fraction，不改变拟合与门限。
3. [完成] 分离phase-seed局部边界与registration-prediction global边界。
4. [完成] 仅在phase失败后的legacy fallback决策中使用新增证据。
5. [完成] 复跑唯一真值、29帧非盲、3控制、静态重复性和一次性10帧holdout。
6. [完成] 全套139测试、compileall、SpecKit analyze、diff与大文件审计后提交推送。

运行时不读取目标真值，不用跨帧中位数修改单帧输出；跨帧只用于发现候选语义矛盾。
