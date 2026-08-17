# Contract: representative diagnostic review

审阅包只复用已有结果与原图生成叠加，不改变检测。所有AUTO标记均为候选证据，`humanVerified=false`。媒体、JSON和CSV写入Git外目录。失败结果的角度、修正量和方向必须保持null。

可移植配置使用`legacy_asset.source_mode=bundled_module`和固定的`algorithms.end_face.core`。`source_sha256`锁定仓库内实际文件，`upstream_source_sha256`记录上游gyj审计源。`annotation_path/reference_path`仍是Git外受控资产，不得内嵌原图。旧配置未声明`source_mode`时按`external_file`解析。
