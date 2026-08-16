#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage:
  smoke_reference.sh REFERENCE_ANNOTATION REFERENCE_IMAGE TARGET_IMAGE OUTPUT_JSON

REFERENCE_ANNOTATION and REFERENCE_IMAGE must be the frozen authoritative
018e/faf manual reference. OUTPUT_JSON must remain outside the Git worktree.
EOF
}

if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
  usage
  exit 0
fi

reference_annotation=${REFERENCE_ANNOTATION:-${1:-}}
reference_image=${REFERENCE_IMAGE:-${2:-}}
target_image=${TARGET_IMAGE:-${3:-}}
output_json=${OUTPUT_JSON:-${4:-}}
if [[ -z $reference_annotation || -z $reference_image || -z $target_image || -z $output_json ]]; then
  usage >&2
  exit 64
fi

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output_json=$(uv run --project "$project_root" python - "$project_root" "$output_json" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).expanduser().resolve()
if output == root or root in output.parents:
    raise SystemExit("OUTPUT_JSON must remain outside the Git worktree")
print(output)
PY
)
mkdir -p -- "$(dirname -- "$output_json")"

uv run --project "$project_root" python "$project_root/tools/run_current_capture.py" \
  --reference-annotation "$reference_annotation" \
  --reference-image "$reference_image" \
  --target-image "$target_image" \
  --config "$project_root/config/current_capture_registration.v1.json" \
  --out "$output_json"
