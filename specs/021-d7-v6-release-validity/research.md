# Research: D7 v6回退首版有效性诊断

## 1. 冻结输入与证据等级

### 用户冻结的Mac独立结果

- 基线：`d15703127f9b80351e42d2819f562553003802d2`。
- 010+030：40/40 D7有效。
- 最新唯一权威同图：真值验收PASS。
- Phi：相对上一版不变。
- 010：20/20来源为`v6_original_quality`回退，A/B边界审核证据不可用。

这些事实证明独立执行状态，不授权读取holdout、降低门限或用真值反向选择候选。

### 服务器只读证据

外置结果`020-final-groups010-030-20260817/current-capture-results.jsonl`包含40条，严格保持
`normal-group-010`与`normal-group-030`身份。仓库没有引入图片、JSONL或运行输出。

## 2. 010逐条质量审计

20条010记录全部满足：

| 字段 | 20帧结果 |
|---|---:|
| `measurementValid` | 20 true |
| `sourceDetector` | 20 `hole2-v6-original-quality-fallback` |
| `recoveryPass` | 20 `v6_original_quality` |
| `d7.quality.upstream` | 20 `ok:dual_boundary_fit` |
| 五个业务量测有限 | 20/20 |
| `evidenceComplete` | 0 true |
| `evidenceAuditStatus` | 20 `unavailable` |
| `evidenceAuditReason` | 20 `boundary_evidence_unavailable` |

原质量字段分布：

| 指标 | 原门/代码条件 | 010 min / median / max |
|---|---|---|
| p1点数 | `>=12` | 31 / 31 / 31 |
| p2点数 | `>=12` | 28 / 28 / 29 |
| p1残差(px) | `<=3.0` | 0.1056 / 0.1380 / 0.2751 |
| p2残差(px) | `<=3.0` | 0.2142 / 0.4033 / 0.4532 |
| p1边缘峰值 | `>=4.0` | 22.2603 / 22.9387 / 23.2685 |
| p2边缘峰值 | `>=4.0` | 25.0735 / 26.0361 / 26.2416 |
| 两边平行度(deg) | v6报告项，不是独立硬门 | 0.3416 / 0.5476 / 0.8151 |
| 端点最大偏移(px) | 每侧必须在42px搜索窗内 | 2.3786 / 3.6881 / 4.9828 |

`detect_dimension_boundary()`还要求拟合线法向与测量轴的余弦不低于`cos(35°)`；只有两侧都返回
`BoundaryDetection`后，v6才写出`ok:dual_boundary_fit`。`_v6_d7_fallback()`不替换这些门，另外只检查
五个业务量测均为有限数。

关键限制：v6会用边缘点拟合，但调用没有传入diagnostics，最终只保留两个交点、长度和聚合质量，
没有保留原始点、内点或A/B有限线段。现有输出无法事后重建真实边界。因此：

- **计算时图像证据存在并通过原门**；
- **交付时可审核几何不存在**；
- 两句话同时成立，不能互相替代。

## 3. 静态重复性只能回答精密度

010的20帧D7：

- mean = 316.5211px
- sample stdev = 0.4501px
- 6sigma = 2.7003px
- range = 1.1683px
- median = 316.8209px
- MAD = 0.0212px

序列中181--185约315.85--315.97px，187--197大多约316.80--316.86px，198又为315.69px。
小MAD与较大6sigma并存，提示存在离散层位/状态跳变风险；20/20有效并不等于20帧绝对准确。
010没有逐帧真值，不能判断哪一簇更接近图纸边界。

相比之下，030的20帧均由paired-transition路径产生且证据完整，mean=303.8065px、sample
stdev=0.1158px、range=0.4104px。两组属于不同零件/位置，不得直接比较均值来判定010偏差。

## 4. 权威单图真值的作用边界

服务器同基线权威报告为PASS：D7长度绝对误差0.5462px，Phi直径绝对误差0.9395px。该帧D7来自
paired-transition路径且证据完整，不是010的v6 fallback。它证明当前主路径在这一张权威样本上满足门，
不能证明010 fallback的绝对误差。

## 5. 方案比较

### 方案A：把010全部改为无效

拒绝。没有证据证明这些数值错误；它们通过既有原质量门，直接清空会改变兼容性契约，并把“未保存审核点”
错误等同于“检测失败”。

### 方案B：继续无条件称为完整有效

拒绝。当前没有A/B原始点或拟合线，操作员无法确认检测的是哪一层；010也没有绝对真值。
只报告20/20会掩盖可审核性和可能的层位跳变。

### 方案C：条件保留技术数值有效（采用）

保留`measurementValid=true`，因为它准确表达“v6原检测质量通过且数值有限”；同时保持
`evidenceComplete=false`、`evidenceAuditStatus=unavailable`、来源和回退路径。首版必须并列报告：

1. D7 measurement-valid计数；
2. D7 evidence-complete计数；
3. v6 fallback计数；
4. `productionDisposition=not_evaluated`。

这类数值可用于技术覆盖率、趋势和后续人工抽检选帧；不得用于“边界已审核”、绝对精度声明或生产OK/NG。
如果首版业务流程要求每个数值都能复核A/B边界，则消费端应要求
`measurementValid && evidenceComplete`，而不是改写底层`measurementValid`。

## 6. 后续解除限制的最小证据

不需要放宽门限。后续优先级应为：

1. 让v6边界检测保留它已经使用的原始点、内点和拟合线，仅补证据可观测性；
2. 用少量冻结、不同零件/位置的D7-A/B人工线验证v6实际边缘层；
3. 验证前保持首版“技术有效但不可审核”的明确警告。

本规格不实施上述代码变更。
