# 配置约定

`detector.groove_shadow_source_discrimination`是严格默认关闭的版本化来源诊断。
它不拥有新的数值门限，只汇总既有ambiguity resolver、v2双壁精修和原始
sidewall source-consistency结果；启用时三者必须同时启用。新物理零件独立
验收前不得进入生产profile，且绝不绕过低`polar_score`或授权PLC输出。

## 槽姿态引导配置

- `legacy_asset.source_mode=bundled_module`是可合并默认：源码只从本仓库
  `algorithms.end_face.core`加载，`source_sha256`校验本地文件，
  `upstream_source_sha256`记录gyj审计源。旧配置未写`source_mode`时按
  `external_file`兼容，但不再是可移植默认。
- LabelMe标注和参考图仍是Git外部署资产，内容哈希必须保持锁定。历史配置不写
  `legacy_asset.path_mode`时按`legacy`兼容原路径语义；跨服务器或Mac部署必须由
  `tools/build_slot_pose_portable_bundle.py`生成单一受控包，并使用
  `path_mode=config_relative_v1`从包内`config.json`所在目录解析两项资产。
  `tools/verify_slot_pose_portable_bundle.py`会独立核验清单、逐文件SHA、bundled core和
  effective config身份。Mac只需要指定Git提交和这一个包，不得再到外部工程目录寻找文件。
- 历史图像坐标原点在左上，方位角随图像y轴向下而顺时针增加。`mechanical_zero_image_deg`与
  `positive_direction=cw|ccw`必须由机械/机器人负责人确认。
- legacy、paired、multi-role和single v1/v2在`conventions_confirmed=false`时只允许诊断候选，正式机械角为空。
  single v3已由负责人确认图像坐标和85°目标，因此可靠检测可输出有效图像帧修正；该值仍不是PLC执行命令。
- `production_plc_mapping_confirmed=false`时不产生PLC地址、缩放整数或写入动作。
- `detector`继续复用历史圆心、尺度和polar链；`groove_recognition`只在同一polar坐标内增加单帧几何硬门，不新建圆/配准系统。
- `detector.diagnostic_mode`只能显式选择`legacy_single_notch`、`paired_notches_centerline`、`multi_notch_roles`或`single_real_groove`，
  程序不会根据图像自动替换目标语义。
- `detector.face_search_roi_normalized`默认不存在；启用时仅在调用原有圆心/尺度链前，以归一化
  `[x_min,y_min,x_max,y_max]`屏蔽相邻工装，候选剖面仍从未裁切原图采样。ROI需在冻结视野上独立验证，
  不代替datum/target映射确认，也不改变fail-closed门。
- `detector.full_frame_circle_locator`默认关闭，且首版只允许在`single_real_groove`下与显式ROI互斥启用。
  它用低分辨率Otsu/连通域产生有限提议，再以180条锁定gyj射线筛选并只让唯一winner进入既有720射线
  物理外圆质量门；连通域边框本身绝不是测量圆。无候选、候选溢出或最佳/次佳差距不足均在槽阶段前失败。
- `detector.physical_outer_circle.edge_family_selection`默认关闭。单拍v3显式开启后，每条射线只采样一次并保留
  有界的亮到暗候选，再以跨角度的完整圆几何预选全局边族；恰好一个族合格才交给原`robust_fit_circle`和原有
  点数、内点率、覆盖、残差、中心漂移及半径比质量门。0个族、多个同心或非同心族、非有限证据和容量溢出
  均在槽链前fail-closed；不得用31°/328°等固定角mask、候选编号、峰强度、目标85°或样本身份打破歧义。
  边族预选先执行，`sector_robustness`仅在唯一族完成原拟合后按既有顺序处理局部残差，不能掩盖多族歧义。
- `pose.target_semantics_confirmed`表示当前显式模式的图像目标实体是否已确认；A2单槽配置可依据
  2026-08-15业务决定设为true，legacy/paired/multi-role不得借此自动确认。它与datum、图纸映射、
  输出用途及零位/正方向相互独立，任何机械门未确认都无正式角。
- paired门限是可解释诊断参数：profile控制环带采样和暗区候选，pairing控制候选数、
  角间距、两侧宽度/显著度比、最佳得分和次优差距。默认值不代表生产阈值已确认。
- multi-role使用`role_assignment`/显式方位窗口分配datum和target，不要求候选总数为2。
  `drawing_datum_definition_confirmed`、`a2_drawing_feature_mapping_confirmed`和`output_purpose`任一未确认时不产生正式纠偏角。
- `multi_notch_roles`中的环形暗区只是`rawCandidates`。`groove_recognition`通过外缘连通深度、
  局部金属对比、左右边缘、轮廓连续性、宽度变化和中心漂移生成`grooveCandidates`；
  角色分配只消费后者。门槛缺省时使用版本化安全默认，但正式验收前仍须冻结配置和原图标签。
- `single_real_groove`复用同一物理外圆和`groove_recognition`，但固定
  `single_groove_pose.expected_accepted_groove_count=1`；v1只输出旧图像方位，v2在唯一槽通过后使用
  `groove_refinement`密集双线性采样、亚像素边缘、稳健侧壁线和外圆交点，输出Y下半轴有符号角、
  左下位置门和`85°±5°`判定。0个/多个槽或任一侧精修失败均不回退到粗角度栅格。
- `single-real-groove-pose-config/3`继续复用v2亚像素几何，但将状态分为检测、图像引导和PLC权限。
  检测可靠时无论当前象限均`valid=true`；图像`+Y`下半轴为0°、顺时针正，到85°取最短环形差，
  `[80,90]`闭区强制输出0°。`production_plc_mapping_confirmed=false`只阻塞机械量和PLC命令，
  不清空`imageFrameCorrectionDeg`。Git安全的显式版本片段为`closed-loop-guidance-v3.fragment.json`。
- `detector.ambiguity_resolution`是默认关闭的有界恢复门。开启后，仅对最多3个已通过粗真槽门的候选逐个运行
  同一套现有亚像素槽壁/外圆交点精修；恰好1个幸存才允许进入姿态，0个、多个或超限均fail-closed。
  它禁止使用候选编号、85°目标、目录类别或验收集得分选槽；独立槽/阴影validation标签完成前不得在生产配置启用。
- `detector.physical_outer_circle.sector_robustness`和`detector.dark_candidate_robustness`也是默认关闭的
  019实验门，且只允许`single_real_groove`启用。前者把既有gyj射线残差按圆周扇区输出；仅当整圆唯一失败项
  是局部残差、异常扇区数量/连续角宽/剩余覆盖均过门时，才复用同一批射线和原`robust_fit_circle`重拟合一次。
  后者在同一条已平滑角剖面上增加有限分位数阈值，并按环形区间去重；最终仍由真槽几何门和“恰好一个”规则决定。
  两者均不得按85°、候选编号、目录或当前数据得分选结果；缺少独立外圆/槽真值前不得改成生产默认。
- `detector.source_consistency_adjudication`是默认不存在/关闭的022开发裁决，只允许在
  `single_real_groove`、020同源性门已开启且槽壁精修v2时显式启用。它不改写020原始
  `sourceConsistency`证据，也不放宽`max_edge_contrast_normalized_difference=0.12`；只有原判定
  精确地仅失败`edge_contrast_asymmetry`、其余原检查全部通过且独立端点结构差不超过版本化门限时，
  才输出`ACCEPTED_OVERRIDE`并继续图像坐标引导。该裁决始终`developmentOnly=true`、
  `authoritative=false`、`plcAllowed=false`，不得进入生产默认配置。
- 单拍初版不新建一套槽门限。使用`tools/prepare_single_shot_initial_config.py`从Git外
  `single_real_groove`基础配置物化时，工具会强制仓内bundled core、单槽v3、85°±5°、
  原020全套同源性门值不变、022裁决版本不变、单拍输入和PLC未确认。它另写
  默认生成`single-shot-initial-profile/3`报告并显式开启经审查的全局圆边族选择；配置和报告都必须放在
  Git工作树外。`--profile-version 2`只为复现旧v2，行为保持不变。v2/v3都仅开启已有的有界
  `ambiguity_resolution`：最多3个粗候选逐个经过同一亚像素双壁、
  外圆交点和同源性门，恰好1个完整通过才解除歧义。它不按分数、编号或固定角度选槽。
- `groove_refinement.threshold_version=groove-sidewall-subpixel-v1`保留历史全点TLS行为；
  `groove-sidewall-subpixel-v2`在严格`max_line_residual_p95_px=2.0`前提下，对槽口圆角/纹理点
  执行有上限的确定性直线共识。它同时要求最少内点、内点率、纵向覆盖和外圆交点一致，
  并对几何不同的次优直线执行支持度差距门。参数均已进入Schema，不得按某张图的点数写死。
- `groove_refinement.wall_edge_family`的`groove-wall-edge-family/2`是031显式启用策略。它先用共享观测纵向区间、
  方向、分离距离和外圆端点把同一物理边的重复响应组成complete-link族，再要求候选壁方向与其外圆端点径向
  几何一致。旧v1若已有唯一代表则原样保留；只有v1无法决定时才启用径向v2恢复，缺少径向证据时回到原v1
  fail-closed结果。仅把一个实际观测到的代表假设送入原唯一性门。它不改变原支持度、残差、coverage或ambiguity
  阈值。`source-consistency-adjudication/3`只在两条径向壁、5轨弯曲槽底、图像检测出的两个固定件及归一化
  槽壁形状/剖面检查全部通过时，允许绝对对比度和梯度强弱差异；任何结构、轮廓、覆盖、端点或固定件排除
  失败都继续fail-closed。旧v1/v2配置行为不变，新策略仍为development-only且不授权PLC。
- 020的`fixture_shadow_model`与`sidewall_source_consistency`默认关闭，且只允许
  `single_real_groove`模式启用。前者把约31度/328度当作可漂移的相机/夹具nuisance prior，禁止做
  ignore mask或候选硬删除；逐候选局部灰度、梯度剖面和成对完整性必须进入诊断。后者要求真实槽两侧壁
  在对比、灰度剖面、径向深度和端点结构上同源，任一硬门失败都fail-closed。没有人工确认的两处阴影区域
  和真实槽边界前，重叠分解保持关闭，不能改成生产默认。
- `paired-capture-slot-pose.example.json`是021双拍编排的安全示例，`enabled=false`不得在仓库内改为true。
  双拍清单把旋转参数状态与数值分开：`UNCONFIRMED`可为空或暂填诊断值，但绝不输出权威引导；只有现场确认
  角度、方向和容差后才能在Git外配置为`CONFIRMED`。第二拍映回第一拍零件坐标采用
  `wrap360(theta2-signedRotation)`；匹配不读取31°/328°固定角屏蔽规则。该层只消费现有单帧完整候选，
  不替换圆拟合、真槽几何或亚像素精修。
- v2侧壁诊断分开`detectedPoints`/`points`/`rejectedPoints`，并记录内点率、覆盖率、
  残差、原始/重拟合/去重候选数和最佳/次佳支持度。只有唯一高质量两侧都通过才计算槽口中点。
- 半径约1646 px时，理想圆周`1 px`弧长约为`0.0348°`；这是分辨率预算，不是生产准确率。
  生产精度必须用原始BMP人工拟合参考、独立复核及冻结validation/acceptance split实测。
- `mm_per_px`为统一保留字段；纯角度输出不使用。`ANGLE_PENDING.limit=null`表示只统计、不判定。
- 静态重复性只按Manifest中显式的同一样品、工位和条件分组，以检测角减同图人工真值角的环形残差统计；
  `groupingExplicit=false`、标注不完整或有效重复不足时不得输出重复性PASS/FAIL。
- Manifest的`split`是评估用途：development/validation/test/acceptance必须按物理样品和源图lineage隔离。
  当前唯一人工标注只能属于development；700张已检查结果属于observed diagnostic回归，不能用来选择阈值或冒充acceptance；
  独立validation/test在新增样品并完成复核前必须报告`NOT_AVAILABLE`。
- 009 canonical inventory的`relative_path`统一相对一个显式`data-root`，只处理清单列出的图；不要把根下normal和
  `坏/`拆成两个含义不同的相对路径基准。Mac若保留`A2/...`前缀，则`data-root`必须是A2的父目录。
- `a2-canonical-inventory.template.csv`是资产清单模板，sample/condition/repeat可空；
  `a2-confirmed-grouping.template.csv`是经负责人确认的分组契约，三字段与authority/provenance必须完整。
  两者不可互换，空draft不得传入显式grouping路径。
- `a2-confirmed-segments.template.csv`是人工确认的连续采集段契约；先用`tools/materialize_a2_grouping.py`
  校验每个class的sequence范围精确覆盖inventory、没有重叠，再生成逐图grouping。段边界不得由算法结果选择。
- 静态重复性资格要求同sample、同condition、连续至少20帧。算法失败帧保留在有效率分母；角度使用环形统计，
  跨组只汇总各组中心化残差。bad组还要求badReason、poseUsable及非算法来源的authority/provenance。
- normal/bad是否为同一物理零件未确认时，sampleId必须使用`normal:`/`bad:`限定，避免错误合并；确认后再由负责人
  提供映射，不得用目录、角度或算法结果反推。
- 过渡盲测锁只消费Manifest/资格表，不接受results参数；冻结后未来开发必须使用导出的development Manifest，
  发布候选只通过`run_transitional_blind_once.py`执行一次。工具在调检测前独占写入execution claim，中断也不允许重跑。
  当前700张的锁永远是非严格过渡证据。
- 019的跨零件鲁棒性验证使用`a2-robustness-parts.template.csv`列出的七个已暴露问题零件，按完整sample生成
  2或3折开发/验证Manifest。工具在打开图片或历史results前以part-006的sample和SHA双重拒绝泄漏；历史审计
  只解析目标SHA行并固定`accuracyEvaluated=false`。这些折用于防止针对单一零件调参，不是严格未见test。

Mac运行时不得提交或拼接本机绝对资产路径。应解压受控便携包并直接使用其中的
`config.json`；包可以移动，资产解析不依赖shell当前目录。算法源码仍来自指定Git提交，
大体积参考资产继续留在Git外。

## A端面与孔2配置

单图 CLI 接收标注、待测图、输出路径、`pixel-size` 和版本化定位质量策略。
`end_face_inspection.example.json` 仅记录部署时应受控的运行字段示例；`end_face_quality.example.json` 是
默认的 `a-end-face-quality-policy/1`。

- `core_source_sha256` 必须与仓库内原样复用核心一致。
- `annotation_path`、参考图和待测图必须位于 Git 仓库外。
- `pixel_size=1.0` 表示只输出像素量；物理标定确认前不得把它解释为毫米。
- 本仓库不保存视觉引导、PLC 地址或机械坐标映射配置。
- `requiredFiniteMetrics` 固定要求中心、尺度和旋转为有限值。
- `scaleRange`、`centerMarginPx` 和 `allowedMethodPrefixes` 只判断端面定位，不修改核心测量结果。
- `orientationEvidence` 要求 polar rotation score 或 notch prominence 至少一项过门限；默认分别为 3 和 12。
- `requiredFeatureLabels` 默认为空；只有经现场评审确认的定位必要特征才可加入。
- 46 的 NCC `0.55`、中间环模板 `0.35`、径向点数/残差和短线峰值规则属于核心固定条件，
  由核心 SHA-256 约束，不在策略中覆盖。

孔2运行配置以 `hole2_inspection.example.json` 为模板复制到外部工作目录，现场值不得直接覆盖模板。

- `calibration.mm_per_px`：毫米/参考像素，必须来自受控标定；为 `null` 时重复性工具只输出像素。
- `feature_mappings`：把算法CSV列映射到稳定业务特征。Φ12.2直接使用
  `Phi12_2_diameter_px`；`Phi12_2_r`作为可追溯的拟合半径保留。
- `tolerance.confirmed=false`：表示不得用于正式OK/NG。
- `repeatability.tiers`：需求中的0.10、0.05、0.03 mm档；当前模板暂以极差评估，口径待确认。
- `current_capture_registration.v1.json` 中 `Φ12.2` 主半径下限固定为 `0.88`；只有主候选在下界饱和时才以 `recovery_min_radius_scale_ratio=0.84` 执行一次恢复搜索。

LabelMe 部分圆弧补全使用 `labelme_circle_completion.example.json`：

- `minimumSourcePoints` 不得低于8。
- `maximumMedianResidualPx` 不得高于核心 `CIRCLE_RESIDUAL_PX=25 px`，配置不能放宽核心门。
- `minimumArcCoverageDeg` 默认 `120°`，用于拒绝不稳定短弧。
- `maximumCompletedUniquePoints` 只是资源安全上限；实际点数始终由圆周长和源点中位间距推导，不是固定契约。
