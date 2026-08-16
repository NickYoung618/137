# Analysis: D7参考剖面相位候选

## Initial evidence

- 权威同图：人工A/B位于成对过渡中点附近，当前正式D7误差约0.55px。
- 581/582：正式成对路径303.7743/303.8430px；人工总距离297.1722/300.0442px。
- 030组正式路径重复性已由Spec 019改善到sample stdev约0.116px、range约0.410px。
- 结论：重复性不是当前主要矛盾；必须区分边缘层选择和人工相位定位。

## Truth boundary

581/582目标LabelMe坐标已以冻结SHA在服务器仓库外提供。检测和候选先在不读取目标标注的情况下
完成；只有离线比较阶段读取D7-A/D7-B。标注、图像、JSONL和运行输出均不进入Git。

## SpecKit consistency

只读analyze覆盖12项FR、5项SC和24项任务；无CRITICAL/HIGH缺口。T019明确由外置坐标JSON阻塞，
不影响候选基础设施和安全旁路交付，但阻止候选晋级正式D7。

## Test-first record

- 红灯：`tests.test_d7_reference_profile`最初因`d7_reference_profile`模块不存在而导入失败。
- 初版纯剖面相关在581/582自然选择约313.35px，证明高相关/低残差不能单独证明边缘相位正确。
- 加入“完整上下文选层 + 成对相反极性过渡按参考无量纲相位定位”后，候选约310.11/310.15px。
- 上述数值均在无目标LabelMe输入下产生；未使用297.1722/300.0442选择或调整候选。
- 因候选仍与正式约304px路径显著分歧且缺逐侧真值，候选保持独立诊断，不接管正式结果。

## Authoritative self-check

- 正式D7：309.4558287715px（保持不变）。
- 独立候选：310.0133096769px。
- 人工端点距离：310.0019912322px；候选长度误差0.0113184447px。
- A/B端点误差：0.0310878717px / 0.0197694270px。
- `formalMeasurementUpdated=false`。

## 581/582 no-truth diagnostic

| Frame | Formal D7 px | Profile candidate px | Candidate status | Truth coordinates used |
|---|---:|---:|---|---|
| 581 | 303.774349 | 310.112100 | valid as diagnostic | no |
| 582 | 303.842993 | 310.153829 | valid as diagnostic | no |

“candidate valid”只表示自身剖面/极性/支持/残差/平行度契约通过，不表示人工精度通过。

## T019 coordinate-level diagnosis

相位定义为同一条成对过渡中`outer=0`、`midpoint=0.5`、`inner=1`。逐侧统计仅保留正式侧拟合线
在既有`3px`残差门内的过渡对；门限没有新增或放宽。

| Frame | Formal / manual / error px | Side | Selected pairs | Manual phase median (MAD) | outer / midpoint / inner median distance px |
|---|---|---|---:|---:|---:|
| 581 | 303.774349 / 297.172226 / 6.602123 | A | 24 | 0.6404 (0.0356) | 8.8408 / **1.9339** / 5.0273 |
| 581 | 同上 | B | 22 | 0.8156 (0.0756) | 11.1697 / 4.3355 / **2.5595** |
| 582 | 303.842993 / 300.044194 / 3.798799 | A | 24 | 0.6022 (0.0314) | 7.9789 / **1.4759** / 5.4368 |
| 582 | 同上 | B | 22 | 0.6100 (0.0692) | 8.4953 / **1.4296** / 5.0071 |

根因分解：A侧两帧均只有约`1.5--1.9px`的中点相位偏移；581的主要额外偏差来自B侧，人工线
落向内过渡，而582的B侧仍最接近中点。020全剖面候选在两帧分别为`310.112100px`和
`310.153829px`，相对人工误差比正式路径更大，因此不能晋级。

两张连续静态帧的人工宽度本身相差`2.8720px`，B侧人工相位也不一致。现有证据不支持把
`0.64`、`0.82`或其他固定相位、固定像素偏移写入运行时；也不支持把B侧一律改成内峰。

## Gates

- 定向候选测试：8/8 PASS。
- 本地孔2基线全套`unittest`（含显式jsonschema）：160/160 PASS，53.575s；rebase到最新
  `origin/main`并纳入远端新增套件后：333/333 PASS，108.345s。
- `compileall -q algorithms tools tests`：PASS。
- `git diff --check`：PASS。
- 配置、Schema、`algorithms/hole_2/main.py`和Phi：无020修改。
- 新增源码/规格无大文件，Git状态无BMP/PNG/JPG/JSONL/压缩包或运行输出。

T019完成后的运行时回归使用Spec 019最终回退契约：

- 权威同图PASS：D7误差=`0.546162px ≤ 2px`，Phi直径误差=`0.939461px ≤ 1px`。
- 9帧execution/registration/D7/Phi=`9/9`/`9/9`/`7/9`/`9/9`；501/520继续拒绝，1830仅由
  v6原质量门回退且证据状态为`unavailable`。
- 010与030各20张均execution/registration/D7/Phi=`20/20`；030全部为约304px的同语义成对
  过渡路径，010全部为受控v6原质量回退。两组都无批量真值，不作准确度结论。

## Final SpecKit analyze

- Functional requirements: `12/12`均映射到任务、实现或验证证据。
- Success criteria: `5/5`均有测试或外置资产结果；SC-003的结论是候选有审计输出但不具备晋级精度。
- Tasks: `24/24`完成；T019不再blocked。
- Constitution conflicts: `0`；目标真值只在冻结后的离线比较读取，所有外置资产未进入Git。
- Critical/high ambiguity, duplication or coverage findings: `0`。唯一残余风险已明确记录：两张人工线的B侧
  相位不一致，不能据此创建统一运行时修正。

## Decision

T019已完成。020候选继续保持**diagnostic only**，正式D7保持Spec 019的同语义成对中点和原质量门。
本轮最小实现只增强离线工具的逐层审计输出，不改变运行时D7、Phi、配置、Schema或门限。若要继续
缩小绝对误差，应先对同一帧做重复盲标或增加冻结的少量D7-A/B验证标注，先量化人工线相位不确定度。
