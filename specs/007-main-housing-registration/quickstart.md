# Quickstart: Main Housing Registration v2

## Verify the pinned anchor

```bash
.venv/bin/python tools/inspect_short_line_labelme.py \
  --labelme /home/ubuntu/disk/dzk/a2-labelme-development-20/a2-short-lines.json
```

## Run the representative anchor

```bash
.venv/bin/python algorithms/end_face/main.py \
  --annotation /path/to/desktop/sample_1_label.json \
  --image /home/ubuntu/disk/dzk/a2-labelme-development-20/representative.bmp \
  --short-line-candidate-config config/end_face_short_line_candidate.v2.json \
  --short-line-labelme-reference /home/ubuntu/disk/dzk/a2-labelme-development-20/a2-short-lines.json \
  --output /tmp/a2-anchor-v2.json
```

This is an anchor result, not evidence for 25-frame improvement.

## Mac external 25-frame comparison

```bash
.venv/bin/python tools/compare_short_line_candidates.py compare \
  --manifest '/Users/daizekai/Desktop/壳体项目/137/manifests/a2-first-25.json' \
  --data-root '/Users/daizekai/Desktop/壳体项目/A2-extracted' \
  --annotation '/Users/daizekai/Desktop/算法/sample_1_label.json' \
  --results-jsonl '/Users/daizekai/Desktop/壳体项目/137/outputs/a2-v2-first-25/results.jsonl' \
  --candidate-config config/end_face_short_line_candidate.v2.json \
  --short-line-labelme-reference '/Users/daizekai/Desktop/壳体项目/137/a2-labelme-development-20/a2-short-lines.json' \
  --output-dir '/Users/daizekai/Desktop/壳体项目/137/outputs/a2-v3-first-25'
```

Adjust only external paths to match the Mac checkout and manifest. Do not copy
the images or generated JSONL into the repository.
