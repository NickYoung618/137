# 配置约定

- `legacy_asset`固定历史源码、LabelMe标注和参考图的绝对路径及SHA-256；换服务器或Mac时只改路径，
  内容哈希必须继续一致。适配器在调用历史函数前校验三项资产。
- 历史图像坐标原点在左上，方位角随图像y轴向下而顺时针增加。`mechanical_zero_image_deg`与
  `positive_direction=cw|ccw`必须由机械/机器人负责人确认。
- `conventions_confirmed=false`时只允许诊断候选，正式角度为空。
- `production_plc_mapping_confirmed=false`时不产生PLC地址、缩放整数或写入动作。
- `detector`继续复用历史圆心、尺度和polar链；`groove_recognition`只在同一polar坐标内增加单帧几何硬门，不新建圆/配准系统。
- `detector.diagnostic_mode`只能显式选择`legacy_single_notch`、`paired_notches_centerline`、`multi_notch_roles`或`single_real_groove`，
  程序不会根据图像自动替换目标语义。
- `detector.face_search_roi_normalized`默认不存在；启用时仅在调用原有圆心/尺度链前，以归一化
  `[x_min,y_min,x_max,y_max]`屏蔽相邻工装，候选剖面仍从未裁切原图采样。ROI需在冻结视野上独立验证，
  不代替datum/target映射确认，也不改变fail-closed门。
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
  `single_groove_pose.expected_accepted_groove_count=1`；恰好一个槽输出版本化图像方位，0个失败、
  多个歧义，不运行datum/target双角色分配，也不自动成为机械纠偏。
- `mm_per_px`为统一保留字段；纯角度输出不使用。`ANGLE_PENDING.limit=null`表示只统计、不判定。

Mac运行时，历史源码、标注和参考图均由本机环境变量或不入Git的配置指向已核验同源文件，
并重新核对哈希。不得把Mac绝对路径提交成服务器默认配置。
