# 配置约定

- `legacy_asset`固定历史源码、LabelMe标注和参考图的绝对路径及SHA-256；换服务器或Mac时只改路径，
  内容哈希必须继续一致。适配器在调用历史函数前校验三项资产。
- 历史图像坐标原点在左上，方位角随图像y轴向下而顺时针增加。`mechanical_zero_image_deg`与
  `positive_direction=cw|ccw`必须由机械/机器人负责人确认。
- `conventions_confirmed=false`时只允许诊断候选，正式角度为空。
- `production_plc_mapping_confirmed=false`时不产生PLC地址、缩放整数或写入动作。
- `detector`门限只使用历史函数已有的notch显著度、polar分数、两路旋转一致性和尺度，不包含新视觉检测器。
- `detector.diagnostic_mode`只能显式选择`legacy_single_notch`或`paired_notches_centerline`，
  程序不会根据图像自动替换目标语义。
- `pose.target_semantics_confirmed=false`表示机械方尚未确认单缺口或双缺口中心线是生产对象；
  该标志与零位/正方向的`conventions_confirmed`相互独立，任一为false都无正式角。
- paired门限是可解释诊断参数：profile控制环带采样和暗区候选，pairing控制候选数、
  角间距、两侧宽度/显著度比、最佳得分和次优差距。默认值不代表生产阈值已确认。
- `mm_per_px`为统一保留字段；纯角度输出不使用。`ANGLE_PENDING.limit=null`表示只统计、不判定。

Mac运行时，历史源码可指向已核验同源文件
`/Users/daizekai/Desktop/壳体项目/work/算法原始/A端面/repeatability_evaluation.py`；标注和参考图也需
指向本机实际文件并重新核对哈希。不得把Mac绝对路径提交成服务器默认配置。
