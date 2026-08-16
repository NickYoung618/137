# Data Model: 孔2最新真值重构

## Runtime additions

### Dimension 7 quality

- `candidate_boundary_semantics`: `paired_edge_centerline`
- `candidate_p1/p2_pair_support`: 成对极性边缘支持数
- `candidate_p1/p2_outer_peak`、`inner_peak`: 跨扫描中位峰值
- `candidate_p1/p2_pair_width_target_px`: 黑色轮廓带宽中位数
- `candidate_p1/p2_fit_residual_target_px`: 中心点云直线残差
- `candidate_boundary_parallelism_deg`: 两中心线平行度

### Phi quality

- `candidate_edge_semantics`: `reference_phase_outer_positive_edge`
- `candidate_reference_edge_phase_fraction`: 仅由旧参考图/标注计算
- `candidate_polarity_enforced`: 主选择是否实际使用带符号极性
- `candidate_phase_edge_points`: 相位边缘点数
- `candidate_phase_fit_residual_target_px`: RANSAC圆残差
- `candidate_phase_angle_coverage_fraction`: 有效点角覆盖

## Offline diagnostic bundle

- `overlay.png`: 绿色最新真值、红色运行时预测。
- `diagnostic-summary.json`: 哈希、误差、梯度极性/物理边界结论。
- `d7-edge-profiles.json`: 显式扫描位置上的正负峰、峰中点和真值偏差。
- `phi-radial-profile.json`: 径向灰度、带符号梯度、预测/真值半径与参考相位。

以上文件必须位于 Git 工作树外。
