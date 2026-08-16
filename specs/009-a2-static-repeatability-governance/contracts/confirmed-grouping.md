# Confirmed Grouping CSV Contract v1

```csv
relative_path,source_image_sha256,sample_id,condition_id,repeat_index,split,dataset_class,grouping_authority,grouping_provenance
A2/normal/frame_0001.bmp,0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef,normal:part-001,fixed-pose-a,1,unassigned,normal,capture_owner,review-20260816
```

- 必须与canonical inventory逐路径、逐SHA、逐class一一覆盖。
- sample/condition/repeat/authority/provenance均不可为空。
- condition内repeat从1连续；一个sample或source SHA不得跨purpose。
- provenance不得引用当前算法结果、角度、有效率或错误码作为分组依据。
