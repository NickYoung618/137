#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_hole2_full_regression.sh REFERENCE_ANNOTATION REFERENCE_IMAGE NORMAL_DIRECTORY DEFECTIVE_DIRECTORY OUTPUT_DIRECTORY [WORKERS]

The paths may instead be supplied with environment variables:
  REFERENCE_ANNOTATION, REFERENCE_IMAGE,
  NORMAL_DIRECTORY, DEFECTIVE_DIRECTORY, OUTPUT_DIRECTORY

Optional environment variables:
  WORKERS (default 4)
  REGISTRATION_CONFIG (default repository config/current_capture_registration.v1.json)

Target annotations are neither accepted nor read. OUTPUT_DIRECTORY must be outside the Git worktree.
EOF
}

if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
  usage
  exit 0
fi

reference_annotation=${REFERENCE_ANNOTATION:-${1:-}}
reference_image=${REFERENCE_IMAGE:-${2:-}}
normal_directory=${NORMAL_DIRECTORY:-${3:-}}
defective_directory=${DEFECTIVE_DIRECTORY:-${4:-}}
output_directory=${OUTPUT_DIRECTORY:-${5:-}}
workers=${WORKERS:-${6:-4}}

if [[ -z $reference_annotation || -z $reference_image || -z $normal_directory || -z $defective_directory || -z $output_directory ]]; then
  usage >&2
  exit 64
fi

script_directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repository_root=$(cd -- "$script_directory/.." && pwd)
registration_config=${REGISTRATION_CONFIG:-$repository_root/config/current_capture_registration.v1.json}

output_directory=$(uv run --project "$repository_root" python - "$repository_root" "$output_directory" <<'PY'
import sys
from pathlib import Path

repository_root = Path(sys.argv[1]).resolve()
output_directory = Path(sys.argv[2]).expanduser().resolve()
if output_directory == repository_root or repository_root in output_directory.parents:
    raise SystemExit("OUTPUT_DIRECTORY must remain outside the Git worktree")
print(output_directory)
PY
)

mkdir -p -- "$output_directory"
log_path=$output_directory/full-regression.log
metadata_path=$output_directory/run-metadata.json
metrics_path=$output_directory/key-metrics.json
metrics_text_path=$output_directory/key-metrics.txt
start_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

exec > >(tee -a "$log_path") 2>&1
echo "startTime=$start_time"
echo "repository=$repository_root"
echo "outputDirectory=$output_directory"

set +e
uv run --project "$repository_root" python "$repository_root/tools/batch_current_capture.py" \
  --reference-annotation "$reference_annotation" \
  --reference-image "$reference_image" \
  --config "$registration_config" \
  --group "normal=$normal_directory" \
  --group "defective=$defective_directory" \
  --output-dir "$output_directory" \
  --workers "$workers"
batch_exit_code=$?
set -e

end_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
printf '{\n  "startTime": "%s",\n  "endTime": "%s",\n  "exitCode": %d\n}\n' \
  "$start_time" "$end_time" "$batch_exit_code" > "$metadata_path"

summary_path=$output_directory/quality-summary.json
if [[ -f $summary_path ]]; then
  uv run --project "$repository_root" python - "$summary_path" "$metrics_path" "$metrics_text_path" <<'PY'
import json
import sys
from pathlib import Path

summary_path, metrics_path, text_path = map(Path, sys.argv[1:])
summary = json.loads(summary_path.read_text(encoding="utf-8"))

def select(stats):
    return {
        "total": stats["total"],
        "registrationValid": stats["registrationValid"],
        "7": stats["featureValid"]["7"],
        "Phi12.2": stats["featureValid"]["Phi12.2"],
        "technicalComplete": stats["technicalComplete"],
        "registrationFailureReasons": stats["registrationFailureReasons"],
        "featureFailureReasons": stats["featureFailureReasons"],
        "timingMs": {
            "mean": stats["timingMs"]["mean"],
            "p50": stats["timingMs"]["p50"],
            "p95": stats["timingMs"]["p95"],
        },
    }

metrics = {
    "schemaVersion": "hole2-full-regression-key-metrics/1",
    "overall": select(summary["overall"]),
    "groups": {name: select(stats) for name, stats in sorted(summary["groups"].items())},
    "evidenceScope": "technical_quality_only_no_target_annotation_no_accuracy_claim",
}
metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = []
for name, stats in [("overall", metrics["overall"]), *metrics["groups"].items()]:
    lines.append(
        f"{name}: total={stats['total']} registrationValid={stats['registrationValid']} "
        f"7={stats['7']} Phi12.2={stats['Phi12.2']} technicalComplete={stats['technicalComplete']} "
        f"timingMs(mean/p50/p95)={stats['timingMs']['mean']}/{stats['timingMs']['p50']}/{stats['timingMs']['p95']}"
    )
    lines.append(f"{name}.registrationFailureReasons={json.dumps(stats['registrationFailureReasons'], ensure_ascii=False, sort_keys=True)}")
    lines.append(f"{name}.featureFailureReasons={json.dumps(stats['featureFailureReasons'], ensure_ascii=False, sort_keys=True)}")
text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
PY
else
  echo "quality summary missing; key metrics were not generated"
fi

echo "endTime=$end_time"
echo "exitCode=$batch_exit_code"
echo "log=$log_path"
echo "metadata=$metadata_path"
[[ ! -f $metrics_path ]] || echo "metrics=$metrics_path"
exit "$batch_exit_code"
