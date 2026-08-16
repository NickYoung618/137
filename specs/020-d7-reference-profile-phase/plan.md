# Implementation Plan: D7参考剖面相位候选

## Summary

在Spec 019正式D7路径旁新增不参与有效性判定的参考剖面候选。候选从唯一权威参考图及其人工D7线
建立每侧法向灰度/梯度上下文，用多条平行扫描、归一化相关、极性和成对过渡一致性定位目标边缘，
然后稳健拟合两条直线并计算公法线距离。外置审核工具在LabelMe坐标可用时逐侧比较；没有坐标时只输出诊断。

## Technical Context

- **Language**: Python 3.11+
- **Libraries**: NumPy、Pillow；不新增OpenCV
- **Integration**: `algorithms/hole_2/current_capture.py`保留正式019 D7，独立模块提供候选
- **Tests**: `unittest`，合成剖面/错误层/失败保护和外置参考自匹配
- **Data**: 图片、目标LabelMe、JSONL及输出全部仓库外
- **Performance**: 候选仅在诊断调用时执行；批量正式运行默认不增加开销

## Constitution Check

- 规格、计划、任务、测试和输出字段可追踪：PASS
- 唯一权威018e/faf参考；退役模板零角色：PASS
- 候选失败安全且不改正式valid/measurement：PASS
- 不输出毫米或OK/NG：PASS
- 大文件与现场数据仓库外：PASS
- 既有核心和Phi不修改：PASS

## Design

### 1. Reference profile model

对D7-A/B分别沿人工测量轴采样，以边界切向多个位置形成剖面集合。每条剖面进行有限值检查、
局部对比度归一化和零均值单位范数处理；聚合灰度模板和一阶差分模板，并记录人工相位为零点。

### 2. Target phase matching

在注册预测边界附近扫描候选轴向位移。每个候选以灰度相关和梯度相关联合评分，并验证参考极性顺序。
对每条平行扫描带做亚像素峰值插值，随后依据相关分数、最佳/次佳margin和跨带位移MAD拒绝歧义。

### 3. Geometry and status

每侧匹配点用现有`robust_fit_line`拟合，复用原支持数、残差、轴向和两侧平行度门。
候选结果只写入独立诊断对象，不覆盖正式D7数值和状态。

### 4. Offline truth comparison

工具读取外置LabelMe的`D7-A`/`D7-B`或明确映射标签，比较人工线与候选拟合线、外/中/内过渡。
只保存坐标误差和证据，不读取标称尺寸、不修改检测结果。

## Project Structure

```text
algorithms/hole_2/d7_reference_profile.py
tools/diagnose_d7_reference_profile.py
tests/test_d7_reference_profile.py
specs/020-d7-reference-profile-phase/
```

## Gates

1. 测试先行，覆盖更强邻层和歧义拒绝。
2. 权威同图每侧误差不超过2px。
3. 正式D7/Phi结果逐值不变。
4. 581/582先产生候选，再用外置坐标JSON离线逐层审核；不得把坐标反馈到检测决策。
5. 全套测试、compileall、Schema、diff、大文件审计通过。
