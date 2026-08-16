# Canonical Inventory CSV Contract v1

UTF-8 CSV：

```csv
relative_path,sample_id,condition_id,repeat_index,capture_sequence,capture_timestamp,split,dataset_class,source_image_sha256
A2/normal/frame_0001.bmp,,,,1,2026-08-13T13:21:12,unassigned,normal,0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

- `relative_path`相对一个明确传入的`--data-root`，安全、规范、唯一。
- inventory只列图，不靠递归发现；源SHA必须唯一且可选核验实际文件。
- draft允许sample/condition/repeat为空且split为unassigned。
- draft不得作为confirmed grouping输入，也不得令Manifest标记groupingExplicit。
