# 配置约定

- `legacy_asset`固定历史源码、LabelMe标注和参考图的绝对路径及SHA-256；换服务器或Mac时只改路径，
  内容哈希必须继续一致。适配器在调用历史函数前校验三项资产。
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
- `groove_refinement.threshold_version=groove-sidewall-subpixel-v1`保留历史全点TLS行为；
  `groove-sidewall-subpixel-v2`在严格`max_line_residual_p95_px=2.0`前提下，对槽口圆角/纹理点
  执行有上限的确定性直线共识。它同时要求最少内点、内点率、纵向覆盖和外圆交点一致，
  并对几何不同的次优直线执行支持度差距门。参数均已进入Schema，不得按某张图的点数写死。
- v2侧壁诊断分开`detectedPoints`/`points`/`rejectedPoints`，并记录内点率、覆盖率、
  残差、原始/重拟合/去重候选数和最佳/次佳支持度。只有唯一高质量两侧都通过才计算槽口中点。
- 半径约1646 px时，理想圆周`1 px`弧长约为`0.0348°`；这是分辨率预算，不是生产准确率。
  生产精度必须用原始BMP人工拟合参考、独立复核及冻结validation/acceptance split实测。
- `mm_per_px`为统一保留字段；纯角度输出不使用。`ANGLE_PENDING.limit=null`表示只统计、不判定。
- 静态重复性只按Manifest中显式的同一样品、工位和条件分组，以检测角减同图人工真值角的环形残差统计；
  `groupingExplicit=false`、标注不完整或有效重复不足时不得输出重复性PASS/FAIL。
- Manifest的`split`是评估用途：development/validation/test/acceptance必须按物理样品和源图lineage隔离。
  当前唯一人工标注只能属于development；700张已检查结果属于锁定acceptance回归，不能用来选择阈值；
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

Mac运行时，历史源码、标注和参考图均由本机环境变量或不入Git的配置指向已核验同源文件，
并重新核对哈希。不得把Mac绝对路径提交成服务器默认配置。
