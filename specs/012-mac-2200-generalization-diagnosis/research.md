# Research: Mac 2200 泛化退化根因

**Evidence date**: 2026-08-15

**Baseline**: `79aa6a4`

**Candidate**: `3ee4b4fce19a6f53eae4bdce4c43d688fc7cf4be`

## 1. Evidence integrity and cohort separation

三份外置JSON的SHA-256已记录在 `spec.md`。两个批次均为 executionSuccess `2200/2200`，
executionErrors为空，且 runtimeInputs 不含目标真值。

### Normal：唯一验收组

| Metric | `79aa6a4` | `3ee4b4f` | Delta | 当前结论 |
|---|---:|---:|---:|---|
| registrationValid | 1962 | 1985 | +23 | 达到 `>=1962` |
| 尺寸7 valid | 1863 | 1772 | -91 | 未达到 `>=1863` |
| Phi valid | 1922 | 1826 | -96 | 未达到 `>=1922` |
| technicalComplete | 1863 | 1772 | -91 | 随尺寸7下降 |
| mean ms | 5798.61 | 6714.00 | +915.39 | 约增加15.8% |
| p50 ms | 5862.78 | 6543.95 | +681.17 | 性能回归风险 |
| p95 ms | 7312.32 | 8645.54 | +1333.22 | 性能回归风险 |

逐图转换：

- registration：lost `0`，gained `23`。
- 尺寸7：lost `136`，gained `45`，净变化 `-91`。
- Phi：lost `135`，gained `39`，净变化 `-96`。

### Defective：仅独立观察

| Metric | `79aa6a4` | `3ee4b4f` | Delta |
|---|---:|---:|---:|
| registrationValid | 148 | 159 | +11 |
| 尺寸7 valid | 93 | 108 | +15 |
| Phi valid | 104 | 109 | +5 |

defective 中尺寸7 lost `3`，均为Phi上游无效；Phi lost `11`，原因为
`phase_radius_out_of_bounds,phase_polarity_support_below_gate`；另有8张geometry rejected。
这些数字不参与normal接受，也不能抵消normal的 `-91/-96`。

## 2. Root cause A：phase score 被套用 legacy magnitude 的0.35门

### 源码语义

`79aa6a4` 的候选峰值来自 `_phi_radius_search_pass`：在二维
`gradient_magnitude(contrast_stretch(target))` 圆周上取统计量，再除以整图二维梯度的
归一量，形成 legacy magnitude peak。

`3ee4b4f` 新增 `_refine_phi_reference_phase`：

1. `_phase_edge_at_angle` 沿每条径向的一维灰度剖面计算有符号梯度，并按参考极性、参考灰度
   相位和局部对比度选择交点；
2. `candidate_phase_edge_peak_normalized` 是这些一维有符号峰的中位数再除以二维梯度归一量；
3. phase拟合成功后，这个值被写回 `selected["edge_peak"]`；
4. `_detect_phi12_2` 随后仍执行
   `selected["edge_peak"] < phi12_2.min_edge_peak_normalized`，配置值为 `0.35`。

因此两种数值虽然都叫 normalized edge peak，但统计对象不同：一个是二维梯度幅值圆周响应，
另一个是平滑后的一维有符号相位峰中位数。没有证据证明它们共享同一个0.35标尺。

### 105张normal证据

筛选条件：旧Phi有效，新Phi无效，唯一最终原因为 `edge_peak_below_gate`。

| Evidence | min | p05 | p50 | p95 | max | Gate |
|---|---:|---:|---:|---:|---:|---:|
| old magnitude peak normalized | 0.73424 | 0.73852 | 0.87093 | 0.98030 | 0.98958 | 0.35 |
| new phase peak normalized | 0.26720 | 0.27240 | 0.34217 | 0.34780 | 0.34966 | 被套用0.35 |
| phase fit residual px | 0.4700 | 0.4897 | 0.6774 | 0.9204 | 1.0555 | 最大3.0 |
| phase edge points | 106 | 113.2 | 196 | 198 | 198 | 最少40 |
| polarity support fraction | 0.7778 | 0.8344 | 1.0000 | 1.0000 | 1.0000 | 最少0.65 |
| angle coverage fraction | 0.6935 | 0.7256 | 0.9799 | 0.9899 | 0.9899 | 最少0.65 |

全部105张的旧source为 `hole2-v6-current-capture-candidate`，新source为
`hole2-v6-current-capture-reference-phase-circle`，`phaseFallback=null` 为105/105。delta没有
通用 `recoveryPass`，因此不对其他恢复分支作推断。

半径比：

- old min/p05/p50/p95/max：`0.88681/0.89007/0.90383/0.99338/1.01595`；
- new min/p05/p50/p95/max：`0.89629/0.89942/0.90897/0.97999/1.00913`；
- new-old差值 min/p05/p50/p95/max：
  `-0.06069/-0.03668/+0.00418/+0.01761/+0.02729`。

这些值证明新相位圆通常具有高支持、低残差、正确极性和大角覆盖，并且半径比未普遍撞界。
它们足以证明当前拒绝规则存在分数语义错配，但在无逐图真值时仍不足以单独证明105张全部是
正确物理边。

### 时间/序号簇

只按文件名末尾数字做连续序号描述，不把20张连续段解释为一个样品或重复组：

`41–60(20)`、`261–280(20)`、`1185(1)`、`1188(1)`、`1193(1)`、`1195(1)`、
`1197(1)`、`1199–1200(2)`、`1361–1371(11)`、`1373–1380(8)`、
`1461–1465(5)`、`1467–1480(14)`、`1621–1640(20)`。

它们集中在拍摄时间约 `21:45:44–21:45:45`、`21:50:09–21:50:10`、
`22:07:41–22:07:42`、`22:11:38–22:11:39`、`22:17:37–22:17:38`，显示问题具有
批次/成像条件相关性，而不是均匀随机噪声。样品级重复性结论仍需要显式manifest。

### 判定

**A成立**：phase score 被继续套用 legacy magnitude `0.35`，存在明确的分数语义不一致。
正确方向是分离两种质量语义并组合独立证据，不是全局降低0.35。

## 3. Root cause B：geometry 从无运行时门变成硬拒绝

### 代码历史

- `79aa6a4`：没有 `evaluate_geometry_consistency`、没有结果级
  `geometryConsistency`，因此既不是运行时硬门，也不是该结果契约内的诊断字段。
- `526c080`：首次加入 `evaluate_geometry_consistency`。当 deviation `>0.08` 时，它把尺寸7和
  Phi的 `measurementValid` 同时改为false、清空target/reference并写入
  `geometry_ratio_inconsistent`。
- `3ee4b4f`：继承上述硬拒绝逻辑；011没有把它从诊断与有效性中解耦。

所以严格说，不是 `3ee4b4f` 单独把旧诊断变硬；相对本次比较基线 `79aa6a4`，硬门由中间提交
`526c080` 引入，并延续到当前候选。历史离线比例统计若存在，也不等于79aa6a4运行时门。

### 批量证据

- baseline geometry rejected：0；candidate normal geometry rejected：36。
- absolute deviation min/p50/max：`0.08364/0.09612/0.11527`，门为 `0.08`。
- 其中30张是两个特征旧版均有效、新版均因geometry变无效，直接构成尺寸7和Phi lost。
- 这30张连续序号主要在 `1321–1360`；最长连续段是 `1344–1360(17)`。
- 其余6张不属于旧有效→新无效的lost；delta changedFrames不足以进一步分类，不能猜测。
- 计算依据是旧参考比例 `0.5412903261`，不是当前2000张normal的人工真值分布。

这36张没有逐图目标标注，也没有证据说明是尺寸7错边、Phi错边、参考/当前域几何差异，还是
二者组合。因此只能称为“比例离群”，不能称为“已证明错边”。

### 判定

**B成立并需精确表述**：`3ee4b4f` 确实执行硬拒绝；`79aa6a4` 没有这个运行时门；硬拒绝最早
在 `526c080` 引入。仅凭 deviation `>0.08` 不能证明36张错边，也不能直接放宽0.08。

## 4. Root cause C：尺寸7净退化主要来自上游耦合

尺寸7 old-valid→new-invalid 共136张：

| New failure | Count | Share of lost |
|---|---:|---:|
| `upstream_phi12_2_candidate_invalid` | 105 | 77.21% |
| `geometry_ratio_inconsistent` | 30 | 22.06% |
| `tangent_boundary_fit_failed` | 1 | 0.74% |

尺寸7新算法自身新增lost只有序号775的一张。其余135张发生在：

- Phi没有通过候选有效性，尺寸7因切线位置依赖Phi而不执行/不输出；或
- 两个特征先有效，之后被统一geometry硬门同时清空。

因此 `1863→1772` 的净退化不能归因于 paired contour 本身。paired contour的准确率和新gained
仍需另行评价，但当前91张净下降主要是上游Phi和组合门耦合。

### 判定

**C成立**。修复顺序应先处理A/B，再观察尺寸7剩余lost；不应为了追回91张而放宽尺寸7自身
的点数、残差、峰值或平行度门。

## 5. 区分正确弱相位边与错误边的候选证据

单一分数不足以判定。下一阶段应保留两套分数并使用以下相互独立证据：

1. **Legacy seed证据**：原二维 magnitude 候选是否通过原峰值、显著性、半径和中心边界门。
2. **Reference-phase证据**：相位点的极性方向必须与旧参考一致；局部绝对梯度峰仍须通过
   `phase_min_edge_score`，不能因归一化语义调整而取消底线。
3. **几何拟合证据**：RANSAC内点数、残差、角覆盖和极性支持分别过门；禁止用一个综合分数
   掩盖任一硬失败。
4. **候选间一致性**：phase圆与通过旧门的seed在中心、半径和可见角上的差异受控；只用于
   一致性/拒绝，不把输出拉向旧值或标称值。
5. **跨帧证据**：在manifest定义的同一样品重复帧中检查圆心、半径和source稳定性；文件名
   连续不能替代manifest。
6. **错边对照**：错误极性、低角覆盖、高残差、少点、撞中心/半径边界和错误背景必须显式失败。

105张当前满足第2、3项的大部分强证据，且旧seed曾通过原门；下一次delta必须补充通用
`recoveryPass`、phase与seed圆心/半径差，才能完整验证第1、4项。

## 6. 定向修复候选（未实施）

### Candidate A1：分离phase与legacy score contract

- 保留 `min_edge_peak_normalized=0.35` 仅用于legacy magnitude候选，不修改其全局值。
- phase候选不得把一维有符号分数再次送入legacy 0.35门。
- phase有效性由绝对相位峰底线、参考极性、局部对比度、点数、RANSAC残差、角覆盖、边界和
  与合格seed的一致性共同决定。
- 结果同时记录两个命名明确的分数及各自passed，避免再次混用。

**主要风险**：移除错误门后可能接受弱但错误的相位圆。必须先用错误极性、背景、低覆盖和
高残差测试证明失败保护，并在105张层做shadow对照。

### Candidate B1：geometry诊断与硬拒绝解耦

- 始终保留 `geometryConsistency` 离群诊断和 `outputAdjustmentApplied=false`。
- 比例可用于候选排序或触发“需要复核”，不得单独清空两个已经通过各自图像门的测量。
- 若保留硬拒绝，必须要求比例离群与独立错边证据同时成立，例如错误极性、低覆盖、高残差、
  候选不稳定或边界饱和；不能只换一个更宽阈值。

**主要风险**：纯诊断可能恢复真正的错边结果。需要构造已知错边候选测试，并对36张输出全部
图像质量证据；没有这些证据前不能宣称36张应全部恢复。

### Candidate C1：优先修复Phi，暂不放宽尺寸7

- A1/B1完成后重新统计尺寸7lost，验证105+30是否随上游语义修正消失。
- 若仍需独立性，可设计只供定位的 `phiGeometryHintValid` 与Phi最终
  `measurementValid` 分离；该hint必须通过半径/中心/残差/覆盖/极性门，且不能把Phi标为有效。
- paired contour自身的点数、残差、峰值、宽度和平行度保持不变。

**主要风险**：错误Phi几何可能把尺寸7搜索轴带到错处，因此hint分离只能作为后续候选，不能与
A1/B1一起无对照上线。

## 7. 结论

当前最小、证据支持的下一步不是降低门限，而是：

1. 测试先行地拆开phase与legacy score contract；
2. 将geometry比例从“单证据硬拒绝”改成可审计的多证据策略；
3. 先观察由此自然恢复的尺寸7，再决定是否拆分Phi定位提示与测量有效性。

本轮没有实施上述候选。
