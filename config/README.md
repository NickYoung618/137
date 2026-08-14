# 配置约定

- `legacy_asset`固定历史源码、LabelMe标注和参考图的绝对路径及SHA-256；换服务器或Mac时只改路径，
  内容哈希必须继续一致。适配器在调用历史函数前校验三项资产。
- 历史图像坐标原点在左上，方位角随图像y轴向下而顺时针增加。`mechanical_zero_image_deg`与
  `positive_direction=cw|ccw`必须由机械/机器人负责人确认。
- `conventions_confirmed=false`时只允许诊断候选，正式角度为空。
- `production_plc_mapping_confirmed=false`时不产生PLC地址、缩放整数或写入动作。
- `detector`继续复用历史圆心、尺度和polar链；`groove_recognition`只在同一polar坐标内增加单帧几何硬门，不新建圆/配准系统。
- `detector.diagnostic_mode`只能显式选择`legacy_single_notch`、`paired_notches_centerline`或`multi_notch_roles`，
  程序不会根据图像自动替换目标语义。
- `detector.face_search_roi_normalized`默认不存在；启用时仅在调用原有圆心/尺度链前，以归一化
  `[x_min,y_min,x_max,y_max]`屏蔽相邻工装，候选剖面仍从未裁切原图采样。ROI需在冻结视野上独立验证，
  不代替datum/target映射确认，也不改变fail-closed门。
- `pose.target_semantics_confirmed=false`表示机械方尚未确认单缺口或双缺口中心线是生产对象；
  该标志与零位/正方向的`conventions_confirmed`相互独立，任一为false都无正式角。
- paired门限是可解释诊断参数：profile控制环带采样和暗区候选，pairing控制候选数、
  角间距、两侧宽度/显著度比、最佳得分和次优差距。默认值不代表生产阈值已确认。
- multi-role使用`role_assignment`/显式方位窗口分配datum和target，不要求候选总数为2。
  `drawing_datum_definition_confirmed`、`a2_drawing_feature_mapping_confirmed`和`output_purpose`任一未确认时不产生正式纠偏角。
- `multi_notch_roles`中的环形暗区只是`rawCandidates`。`groove_recognition`通过外缘连通深度、
  局部金属对比、左右边缘、轮廓连续性、宽度变化和中心漂移生成`grooveCandidates`；
  角色分配只消费后者。门槛缺省时使用版本化安全默认，但正式验收前仍须冻结配置和原图标签。
- `mm_per_px`为统一保留字段；纯角度输出不使用。`ANGLE_PENDING.limit=null`表示只统计、不判定。

Mac运行时，历史源码、标注和参考图均由本机环境变量或不入Git的配置指向已核验同源文件，
并重新核对哈希。不得把Mac绝对路径提交成服务器默认配置。
