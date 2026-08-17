# Evidence: 真槽同源性误拒裁决

## Baseline

- Branch base: `021-paired-capture-slot-pose@ec621118c7d09669cc6ae3ea10c6b80ef3780ea7`.
- New branch: `022-source-consistency-adjudication`.
- Worktree was clean before specification; no main merge or PLC/HMI authorization.
- Existing original contrast threshold remains `0.12`; old candidate remains default-off and non-promoting.

## Authoritative external evidence boundary

- 145 long-arc evaluation: 46 independent outer-circle points, `124.922561°` coverage,
  `humanCurrentAngleDeg=29.591762332111`, AUTO candidate `29.578393924928`, circular error
  `-0.013368407183°`, geometry MVP window true.
- 145 runtime remains rejected only by `edge_contrast_asymmetry`; this is the positive false-rejection case.
- 147 has human-confirmed clean same-groove walls and shoulder endpoints, but no independent outer-circle truth;
  it cannot support a final angle-accuracy claim.
- part-019 is the authoritative mixed real-wall + fixture-edge negative. Its stable angle is a stable false positive,
  not a recovery.
- All images, LabelMe, JSONL and reports remain Git-external. Runtime must not consume evidence identity or geometry.

## Server implementation evidence

- TDD红门先证明模块、运行时释放和契约约束均不存在；实现后聚焦测试通过。
- Git外实验配置由只读物化工具生成，SHA-256为
  `5e4d87130c3528398f6671a6ab2ace4fcf4cac09b9e28bde570af1c2822434dc`；原020对比度门仍为`0.12`。
- 145：原判定只失败`edge_contrast_asymmetry`，contrast差`0.1835436047`，端点结构差
  `0.0202945454`；新裁决`ACCEPTED_OVERRIDE`，图像角`29.5783939249°`、顺时针修正
  `+55.4216060751°`，机械修正和PLC均为空。对独立长弧真值的既有误差仍为`-0.013368407183°`。
- 147：原contrast差`0.1829608929`、端点结构差`0.0205143048`，新裁决
  `ACCEPTED_OVERRIDE`，图像角`29.5793431273°`、顺时针修正`+55.4206568727°`，PLC为空；
  因无独立外圆真值，不作最终角度准确率结论。
- part-019代表374：原contrast差`0.1313834797`，端点结构差`0.0764119002`，新裁决
  `REJECTED`（`strict_endpoint_structure`），继续`GROOVE_SOURCE_INCONSISTENT`；图像角、修正方向、
  机械修正和PLC全部为空。
- 非sealed 140张三折实验回放：`13/140`运行时图像姿态有效，全部来自part-008原有13个完整候选；
  part-008其余7张仍为`HOUSING_CIRCLE_NOT_FOUND`。part-019 `20/20`继续
  `GROOVE_SOURCE_INCONSISTENT`且裁决`REJECTED`；part-009/014/015/021/023分别保持原
  圆定位、槽歧义、槽缺失、槽精修、物理圆失败，均未被越过。裁决计数为
  `ACCEPTED_OVERRIDE=13`、`REJECTED=20`、`NOT_EVALUATED=20`，另外87张在更早阶段停止；
  `plcCommandNonNullCount=0`。
- 与`ec62111`默认关闭基线按`taskId`逐条比较，53个实际产生020同源性诊断的
  `diagnostics.grooveSourceConsistency`对象结构化等值，差异`0/53`；022只新增独立裁决payload。
- 这`13/140`只是默认关闭实验配置下的自动有效率，不是准确率；145有独立角真值，147仅有洁净双壁语义，
  part-008其余11张无人工真值。Mac独立回放仍是合并前外部门，且本分支不合main。
- 服务器聚焦门`60/60`通过；全量`466/466`通过。根Schema `45/45`通过Draft 2020-12检查；
  53条真实裁决payload全部通过专用Schema。5000次纯标量裁决P50/P95/max为
  `0.057840/0.091517/0.744087 ms`，低于5 ms门；CLI help、JSON、编译、`git diff --check`通过。
