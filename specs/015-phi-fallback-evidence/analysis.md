# SpecKit Analyze: Phi回退证据与累计圆心边界

**Status**: Server gates passed; pending Mac 2200 regression

## Checklist

- 新判断是否复用现有门限而非降低/增加针对性常数。
- local recenter与global registration-prediction边界是否命名清楚。
- phase成功是否不受legacy fallback保护条件影响。
- 唯一真值、521极性回退和500/620控制是否保持。
- D7门限是否完全不变。
- normal、holdout、defective是否分别报告。

## Analyze result

- 配置文件未修改；0.88→0.84、legacy 0.35以及全部注册、D7、geometry门保持原值。
- 新inlier fraction复用现有`min_angle_coverage_fraction=0.65`，没有引入按帧或尺寸常数。
- phase局部边界现相对phase seed；global边界相对原注册预测，字段和决策用途分离。
- phase成功不受legacy fallback保护条件限制；phase失败且global越界时才拒绝fallback。
- 500/521/620状态保持；521的133/139高内点率legacy回退保持有效。
- 520的76/155低内点率被拒绝；623同时有半径、覆盖及global风险而被拒绝。
- 尺寸7检测器、配置和质量门未改。它只因Phi确实无效而在520/623显示上游无效；501的Phi
  强phase成立后，7仍须通过原v6质量门。
- 唯一真值精度保持；无标注29张与holdout 10张只作行为证据，未声明准确率。
- defective始终独立报告，没有计入normal。
- 静态重复性已成为必报指标，但当前每组不足20帧，正确结论是`INCOMPLETE`。
- SpecKit活动规格已指向015，prerequisites通过；139个测试、compileall、diff check和大文件审计
  通过。

## Remaining risk

服务器样本无法估计2000张normal的净状态变化，尤其需观察520/512型弱相位拒绝与501型强相位
恢复的总体数量。Mac接受门仍是registration>=1962、7>=1863、Phi>=1922，geometry同定义离群
不增加，唯一真值误差不退化；并新增20帧静态重复性分布审计。
