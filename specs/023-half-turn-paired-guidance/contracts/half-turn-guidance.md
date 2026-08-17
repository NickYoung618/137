# Contract: half-turn guidance v1

两种请求使用同一结果契约。`SINGLE_CAPTURE`包含一拍，`HALF_TURN_PAIR`包含同件两拍。双拍半圈固定180°且方向无关，不接收硬件实际反馈。

角度约定：图像x向右、y向下；以y下半轴为0°；顺时针正。`currentAngle=wrap180(profileAzimuth-90)`。`correctionRaw=wrapTo180PreferPositive(85-currentAngle)`；80°至90°内输出0/NONE，精确半圈输出+180/CLOCKWISE。

双拍归一化：`capture2InCapture1=wrap360(capture2Profile-180)`。两拍均可靠时由capture2直接输出；只有capture1可靠时，`capture2Profile=wrap360(capture1Profile+180)`。禁止按离目标远近选候选。

所有输出均为开发阶段image-frame guidance；`authoritative=false`、`posePromotionAllowed=false`、PLC字段为空。
