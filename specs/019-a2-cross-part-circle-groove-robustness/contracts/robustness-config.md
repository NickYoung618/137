# Contract: Robustness Configuration

顶层仍为slot-pose-config/1。旧配置缺少新块时按enabled=false处理。新块只允许在
single_real_groove路径启用。

示例字段：

    detector.dark_candidate_robustness:
      schema_version: angular-dark-candidate-robustness/1
      enabled: false
      quantile_levels: [0.05, 0.10]
      max_hypotheses: 3
      dedup_center_deg: 2.0
      min_interval_overlap_ratio: 0.5

    detector.physical_outer_circle.sector_robustness:
      schema_version: physical-circle-sector-robustness/1
      enabled: false
      sector_bin_count: 36
      min_points_per_sector: 3
      suspect_residual_p95_multiplier: 1.0
      max_excluded_sector_count: 4
      max_contiguous_excluded_deg: 40.0
      min_retained_angular_coverage: 0.72
      max_refit_center_delta_px: 3.0
      max_refit_radius_delta_px: 3.0

配置验证拒绝未知版本、布尔值伪装数值、非有限数、不递增或重复分位数、假设数不相容、
排除扇区不小于总扇区和无法满足保留覆盖的组合。
