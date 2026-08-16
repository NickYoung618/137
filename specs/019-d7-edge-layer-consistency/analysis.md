# Analysis: 030组D7边缘层切换

## Evidence boundary

- Mac外置人工对照：581=`297.1722px`，582=`300.0442px`；服务器不持有这两份LabelMe JSON。
- 服务器可用：100张无真值图、批量JSONL、质量证据和审核图。
- 本结论只确认317px恢复层疑似错边；不将其付96张或全100张当作绝对精度样本。

## Root cause chain

1. 581的paired-transition主路径两侧都通过，输出`303.774349px`。
2. 582的paired-transition A侧通过；B侧原始候选存在主导层与少数邻近层。自由TLS被邻近层拉斜，
   残差`7.157743px`超过原`3px`门，所以主路径拒绝是正确的。
3. multiband恢复没有继续使用成对过渡中点，而是每条剖面选单个最强梯度。`-24/0/+24px`三带
   都选中同一个更外层，因此一致性、平行度、残差和峰值均通过，但输出`317.153840px`。
4. 因此问题不是现有质量门太严或太松，而是恢复前后的物理边界定义不同。

## Decision

实施最小D7改动：初次paired-transition因方向/残差失败时，在相同成对过渡中点上执行稳健主导层拟合；
最终仍使用原支持数、`3px`残差、轴向和平行度门。不再让单梯度multiband候选直接成为有效D7。

## Risks and protections

- **风险：两层对等支持**。保护：无法在原残差门内形成足够主导支持时拒绝。
- **风险：修改原有有效帧**。保护：只在初拟合失败后进入新路径；581逐值不变测试。
- **风险：用两张真值过拟合**。保护：测试不包含297/300目标值；只验证路径语义、安全拒绝和原门。
- **风险：影响Phi**。保护：Phi代码零改动，权威同图/9帧/030组逐值对比。

## Implemented candidate

- 初始paired-transition已通过时不做任何重拟合。
- 仅当初拟合因轴向或残差失败时，用中位成对斜率在扫描坐标系中建立主导层；内点仍由原`3px`
  残差门选取，并重跑原支持数、轴向、残差、平行度和搜索边界门。
- 单梯度multiband仍产生诊断，但不再能直接使D7有效。若新候选失败，独立v6结果只有在其原始
  `ok:dual_boundary_fit`质量门通过时才能回退；回退结果明确标记`evidenceAuditStatus=unavailable`，
  不伪装成具有新式A/B边界证据。
- 配置、D7原质量门和Phi代码零改动；没有真值、文件名、标称值或像素补偿进入运行时。

## Real 581/582 verification

| Frame | Manual distance (offline only) | Baseline | New | Decision |
|---|---:|---:|---:|---|
| 581 | 297.1722 | 303.774349 primary | 303.774349 primary | 主路径和逐值完全不变 |
| 582 | 300.0442 | 317.153840 single-gradient multiband | 303.842993 paired-layer stabilization | 错边缘层被消除 |

- 582的B侧从27个成对中点中保留22个主导层支持；最终残差`0.5474px`、轴余弦`0.9966`，
  全部使用原门。
- 581/582对人工距离的绝对误差仍分别为`6.6021px`/`3.7988px`，所以本增量只证明恢复边缘层一致，
  不声称两张已达到`2px`绝对精度。

## 030 group verification (unlabeled repeatability only)

- execution/registration/D7/Phi: `20/20` / `20/20` / `20/20` / `20/20`。
- 旧8张primary保持逐值不变；旧12张`316.519–319.590px` multiband结果全部转为
  `303.626–304.036px` paired-layer结果。
- D7 mean=`303.806504px`，sample stdev=`0.115782px`，6σ=`0.694694px`，range=`0.410391px`，
  MAD=`0.080875px`。旧range=`15.879416px`、旧stdev=`6.779066px`。
- Phi逐帧直径最大绝对差=`0.0px`。
- 上述20张无真值，只支持路径一致性和静态重复性结论，不支持绝对准确度。

## 010 control-group regression

- execution/registration/D7/Phi=`20/20`/`20/20`/`20/20`/`20/20`，相对`2341ba4`有效状态变化为0。
- 010的成对过渡证据不足，20张均仅由`v6_original_quality`回退；每张都通过v6原始
  `ok:dual_boundary_fit`门，并明确标记新式边界证据`unavailable`。
- D7 mean=`316.521126px`、sample stdev=`0.450053px`、6σ=`2.700320px`、range=`1.168265px`、
  MAD=`0.021158px`。该组无人工真值，这些数值只证明状态兼容和静态重复性，不证明该边缘层准确。
- Phi逐帧差异不超过`5.7e-13px`；注册变换差异不超过`1.2e-12px`，均为浮点舍入量级。

## Safety set and truth anchor

- 9帧：execution=`9/9`、registration=`9/9`、Phi=`9/9`、D7=`7/9`。501/520的v6原质量门也失败，
  因而继续明确拒绝。
- 620由paired-layer证据恢复且通过原门。
- 1830的新成对路径证据不足，但v6原始`ok:dual_boundary_fit`门通过，因此回退为
  `hole2-v6-original-quality-fallback`，目标图值`315.657230px`，并明确标记边界证据不可审核。
  该帧无真值，不宣称该数值准确；这里只验证回退契约与基线有效状态没有被隐藏改变。
- 权威同图：D7绝对误差`0.546162px ≤ 2px`，Phi直径绝对误差`0.939461px ≤ 1px`，PASS；
  与基线逐值相同。

## Engineering verification

- `uv run --with jsonschema python -m unittest discover -s tests -p 'test_*.py'`: `152/152` PASS。
- 显式Schema/契约套件：`35/35` PASS。
- `compileall`: PASS。
- SpecKit prerequisites正确解析到019。
- `git diff --check`、配置/Phi diff、大文件和运行产物审计：PASS。

## SpecKit analyze

- Functional requirements: `12/12` mapped to tasks and verification evidence.
- Success criteria: `5/5` mapped to real/synthetic verification.
- Constitution conflicts: `0`.
- Unmapped implementation tasks: `0`.
- Critical/high ambiguity, duplication or coverage findings: `0`.
- The residual evidence risks remain explicit rather than hidden: 581/582 manual distances do not establish a
  `≤2px` accuracy result, and v6-gated fallback values remain valid-but-unauditable until separately labelled.
