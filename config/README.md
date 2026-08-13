# 配置约定

当前单图 CLI 直接接收标注、待测图、输出路径和 `pixel-size`，不隐式加载机器相关配置。
`inspection.example.json` 仅记录部署时应受控的字段示例。

- `core_source_sha256` 必须与仓库内原样复用核心一致。
- `annotation_path`、参考图和待测图必须位于 Git 仓库外。
- `pixel_size=1.0` 表示只输出像素量；物理标定确认前不得把它解释为毫米。
- 本仓库不保存视觉引导、PLC 地址或机械坐标映射配置。
