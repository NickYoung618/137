# Analysis: D7可审核直边支持

## Root cause

1. **检测几何不是曲线**：581/582的A/B本来就是共同法向的严格直线；LabelMe也是`line`两点对象。
2. **支持范围局部且混合方向**：旧显示段来自公法线附近`±36px`扫描，一半朝圆柱连接区，一半朝窄颈，
   因此在全图缩小后既短又容易被纹理掩盖。
3. **renderer缺少审核上下文**：旧预览只按端点画线，没有A/B标签或局部放大；JPEG缩放没有把直线变成曲线，
   但让短段难以肉眼判断。
4. **010是独立证据缺口**：v6回退实际执行过两侧单梯度拟合，但冻结核心没有交付diagnostics，适配层也不能
   把这种单梯度层冒充当前paired-transition中点语义，所以此前没有A/B。

## Evidence-driven decision

曾尝试只沿窄颈方向在现有band offsets继续收集paired支持。581/582的A侧最多到约48--72px偏移，B侧在
24px后即缺少足够同语义支持。用单梯度可以获得更长线段，但合成暗边测试证明它落在光学边带一侧，与paired
中点相差4px并被原3px残差门拒绝；Spec 019/020也已证明单梯度恢复可能选到约317px错误层。

因此最终不“为了好看”撑长正式A/B：

- 正式A/B只使用已经通过原质量门的paired中点，并只保留公法线向窄颈方向的点；有限显示端点是这些点在
  冻结直线上的投影。圆柱侧点被裁掉，D7交点、直线方程和数值不重算。
- 预览左下提供D7 DETAIL局部放大、A/B标签和公法线，解决全图下“不像直线”的审核问题。
- v6回退在适配层以同一最终变换、参考极性和冻结检测函数确定性重放。只有两侧重放交点与正式v6交点在
  数值精度内一致，才输出紫色`REVIEW`点线；正式boundaries仍为空，证据状态仍`unavailable`。

## Test-first record

- 初始红灯：缺少支持裁剪接口、v6 review契约字段和两套renderer的REVIEW形状，定向套件出现1 failure、3 errors。
- 安全红灯：单梯度扩充在合成暗边上与paired中心线相差4px，测试拒绝了这条错误扩充路线。
- 最终定向套件：`61/61 PASS`，覆盖向外裁剪、端点共线、无证据不延长、v6交点一致性、REVIEW隔离、
  LabelMe标签和D7局部放大。

## Authoritative truth anchor

唯一权威同图验收继续PASS：

| Feature | absolute error | gate |
|---|---:|---:|
| D7 | 0.546162px | <=2px |
| Phi12.2 diameter | 0.939461px | <=1px |

检测运行时未读取truth JSON；truth只在离线evaluate步骤读取。

## Representative visual audit

仓库外目录：`/home/ubuntu/disk/dzk/hole2-d7-audit-022-20260817/review-final/`。

- 581/582/981：橙色A/B严格共线、只覆盖向窄颈方向的paired原始支持；青色公法线独立显示；左下局部放大
  明确标出A/B。没有把圆弧、圆角或更远单梯度层画成正式轮廓。
- 181（010）：紫色v6 A/B及连接线可见，顶部继续显示`evidence=unavailable`；LabelMe flags固定为
  `reviewOnly=true`、`equivalentToFormalBoundary=false`。

## Five-group 100-frame regression

五个显式20帧组分别运行后合并统计；没有把100帧误当成一个静态重复组。

- execution/registration/D7/Phi/both=`100/100/100/100/100`。
- 相对既有010/030最终JSONL及050/080/100基线JSONL：状态变化`0`，D7/Phi数值变化`0`（绝对容差`1e-9px`）。
- 正式paired证据80帧；v6 review 20帧，20帧均保持`evidenceAuditStatus=unavailable`。
- 100帧所有正式A/B显示端点均满足各自直线方程，几何异常数`0`。

### Per-group static repeatability (unlabeled; diagnostic only)

| group | D7 mean / stdev / 6sigma / range / MAD px | Phi mean / stdev / 6sigma / range / MAD px |
|---|---|---|
| 010 | 316.521126 / 0.450053 / 2.700320 / 1.168265 / 0.021158 | 538.178431 / 0.103114 / 0.618685 / 0.426784 / 0.041980 |
| 030 | 303.806504 / 0.115782 / 0.694694 / 0.410391 / 0.080875 | 542.168277 / 1.459433 / 8.756598 / 5.165482 / 0.800341 |
| 050 | 304.524826 / 0.057682 / 0.346091 / 0.198594 / 0.028852 | 540.347186 / 0.176288 / 1.057729 / 0.921465 / 0.024197 |
| 080 | 305.849670 / 0.061521 / 0.369128 / 0.204607 / 0.044998 | 545.714420 / 0.515701 / 3.094208 / 2.676517 / 0.211235 |
| 100 | 307.034176 / 0.179903 / 1.079421 / 0.602547 / 0.116626 | 542.078402 / 0.334643 / 2.007861 / 1.235438 / 0.210204 |

这些100张无逐图真值，只验证技术完成率、数值非回归和组内重复性，不产生绝对准确度结论。

## Frozen components and external evidence

- `algorithms/hole_2/main.py`工作树与HEAD SHA-256均为
  `77fec0bbdaa86f57a89b88bc185b7295237addc99cf2fbf6e91e958a372b2564`。
- `config/current_capture_registration.v1.json`工作树与HEAD SHA-256均为
  `5076329ad4753db2d6c2847af939fd6c5539ed01d148b70c054018ccce5e20d4`。
- Phi、配置、Schema、质量门和业务测量列无本轮差异。
- BMP、JSONL、JPEG/PNG、LabelMe预测和所有运行结果均留在仓库外。

## Final gate status

- **Unittest**：340个不同测试全部取得绿色结果。受双核服务器同时运行外部.NET/Python计算影响，单进程
  discovery中的历史端面适配器`<8s`墙钟断言出现环境抖动；按模块分段覆盖为139 PASS、87个非性能用例
  PASS、113 PASS，唯一性能用例在空载隔离复跑PASS。没有修改该历史测试或性能门。
- **定向测试**：新增/相关61 PASS；契约及JSON Schema 16 PASS。
- **静态门禁**：`python -m compileall -q algorithms tools tests`、`git diff --check`均PASS。
- **SpecKit**：prerequisites PASS；只读analyze覆盖13项FR、6项SC和24项任务，无缺失需求映射、无
  `NEEDS CLARIFICATION`、无Critical/High问题。
- **冻结审计**：`main.py`与配置SHA和HEAD一致；Phi、配置、Schema、质量门无差异；运行时代码无
  `cc192`、`da223`或`registration_reference`残留。
- **Git内容审计**：变更清单无BMP、PNG/JPEG、JSONL、LabelMe预测或运行目录；超过5MB的文件仅为
  既有`.venv`依赖，不在本次diff中。所有真实图片与审核产物保持仓库外置。

结论：SC-001至SC-006均有证据覆盖，可以提交。Mac仍需从GitHub复核新的局部放大和紫色REVIEW显示；
这一步是人工显示验收，不改变本轮100帧技术/数值非回归结论。
