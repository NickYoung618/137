# Analysis: D7 v6回退首版有效性决策

## Executive decision

**010的v6原质量回退可以在初始技术版本继续保持`measurementValid=true`，但只能是“条件保留”。**

它必须同时保持`evidenceComplete=false`、`evidenceAuditStatus=unavailable`并明确v6来源；不得被称为
边界可审核、绝对精度已证明或生产OK/NG。如果首版某个消费场景要求人工可复核边界，该场景必须要求
`measurementValid && evidenceComplete`，而不是改写底层测量状态。

## Mac extension confirmation

Mac在相同`d1570312`运行时代码上完成050/080/100新增60帧独立复验，execution、registration、D7和Phi
均为60/60；合并既有010/030后，5组100帧达到100/100技术完成且无帧级失败。唯一权威真值仍PASS：
D7误差0.546162px、Phi直径误差0.939461px。

因此，**初始技术版本状态确认为可交付，且继续受本规格的条件发布边界约束**。这批60帧没有目标真值，
不能把100/100解释为100张精度通过；010的20帧仍是`measurementValid=true`但
`evidenceComplete=false`；`productionDisposition`仍为`not_evaluated`。本次记录不触发调参或算法修改。

## Root cause

010的新paired-transition候选在A/B两侧不能形成合格的同层边界，因此正式逻辑进入受控v6 fallback。
v6不是直接复用模板线：它在目标图上按两侧参考极性分别扫描，收集边缘点并稳健拟合边界。010的20帧中，
两侧点数、峰值、残差、轴向和搜索窗条件均通过，`upstream`因此为`ok:dual_boundary_fit`。

不可审核的直接原因是**证据保留链断开**：v6调用边界检测时没有收集/序列化diagnostics，只留下两侧交点、
距离和汇总质量。适配层不得从交点伪造边界A/B，所以正确输出为空`boundaries`和`unavailable`。

这属于交付可观测性缺口，不等于检测器计算时没有图像证据；但它也不允许我们声称检测到了可复核的具体边缘层。

## Evidence sufficiency

### 支持保留技术有效性的证据

- Mac独立010+030为40/40有效，执行链无本轮状态问题。
- 010全部20帧明确来自受控v6 fallback，原质量状态均通过且五项业务值有限。
- 010两侧点数远高于12点门，峰值远高于4.0门，最大残差低于0.454px而门为3.0px。
- 平行度虽不是v6单独硬门，但20帧报告值均低于0.816°，没有几何发散信号。
- 失败保护测试确认原状态失败或非有限值不会恢复。

### 不足以证明准确度的证据

- 010没有人工D7-A/B真值。
- 010的20帧重复性存在约1.168px全范围和离散层位跳变迹象；重复性不能排除共同系统偏差。
- 权威单图PASS来自证据完整的paired-transition主路径，不是v6 fallback，不能外推到010。
- 当前结果无法显示v6实际拟合的A/B线，操作员不能逐帧确认边缘身份。

## Alternatives and decision

| 方案 | 结论 | 理由 |
|---|---|---|
| 全部改无效 | 不采用 | 把证据未保存误当成检测失败，破坏既有兼容语义 |
| 无条件完整有效 | 不采用 | 掩盖审核缺口和无真值限制 |
| 条件保留技术有效 | 采用 | 保留原质量判断，同时用独立证据轴和使用权限控制风险 |

## Initial-release rules

1. `measurementValid=true`只回答“原检测质量是否通过并给出有限数值”。
2. `evidenceComplete=false`回答“当前交付是否能复核A/B边缘”；010答案为否。
3. 报告必须同时列出measurement-valid、evidence-complete和v6-fallback数量。010分别为20、0、20。
4. 审核图不得补画假的A/B线；尺寸连接线必须标明只是measurement annotation。
5. 010可用于技术覆盖率、趋势和后续抽检选帧，不可用于绝对精度或生产OK/NG。
6. Phi算法和结果不受本决策影响。

## No-change verification

- 未修改`algorithms/`、`config/`、`schemas/`、`tools/`或`tests/`。
- 未降低任何门限，未使用真值选择候选，未改Phi。
- 定向契约测试2/2通过，覆盖测量/证据独立语义和v6失败不恢复。
- 本规格只形成首版解释和发布边界，不声称Mac 010绝对精度通过。

## SpecKit analyze result

- prerequisites正确解析到`specs/021-d7-v6-release-validity`，所需设计文档与任务齐全。
- 10项FR、5项SC均有research、contract或验证任务覆盖；无澄清标记或模板占位符。
- Constitution的数据最小化、安全失败、输入输出可追溯和非生产判定要求均满足。
- `git diff --check`通过；021目录最大文件小于6KB，不含BMP、JSONL、PNG、JPG或运行输出。
- 唯一工作树变化是未提交的SpecKit 021文档；未修改运行时与质量门。

## Follow-up, not part of this increment

如需把010升级为可审核结果，最小工程方向是保留v6已经使用的raw/inlier points和两条拟合线，再用少量冻结的
不同零件/位置人工A/B标注进行独立验证。该工作应单独建Spec，不能通过放宽门限或固定像素补偿替代。
