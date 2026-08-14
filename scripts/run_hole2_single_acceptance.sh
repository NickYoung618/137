#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_hole2_single_acceptance.sh REFERENCE_ANNOTATION REFERENCE_IMAGE TARGET_IMAGE LATEST_TRUTH_JSON OUTPUT_DIRECTORY

The five paths may instead be supplied with environment variables:
  REFERENCE_ANNOTATION, REFERENCE_IMAGE, TARGET_IMAGE,
  LATEST_TRUTH_JSON, OUTPUT_DIRECTORY

Optional environment variable:
  REGISTRATION_CONFIG (default repository config/current_capture_registration.v1.json)

The detector never receives LATEST_TRUTH_JSON. The truth is read only by the
second, offline acceptance step. OUTPUT_DIRECTORY must be outside the Git worktree.
EOF
}

if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
  usage
  exit 0
fi

reference_annotation=${REFERENCE_ANNOTATION:-${1:-}}
reference_image=${REFERENCE_IMAGE:-${2:-}}
target_image=${TARGET_IMAGE:-${3:-}}
latest_truth_json=${LATEST_TRUTH_JSON:-${4:-}}
output_directory=${OUTPUT_DIRECTORY:-${5:-}}

if [[ -z $reference_annotation || -z $reference_image || -z $target_image || -z $latest_truth_json || -z $output_directory ]]; then
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
stdout_log=$output_directory/stdout.log
stderr_log=$output_directory/stderr.log
metadata_path=$output_directory/run-metadata.json
result_path=$output_directory/algorithm-result.json
acceptance_path=$output_directory/acceptance-report.json
metrics_path=$output_directory/key-metrics.json
metrics_text_path=$output_directory/key-metrics.txt
exit_code_path=$output_directory/exit-code.txt
start_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

exec > >(tee -a "$stdout_log") 2> >(tee -a "$stderr_log" >&2)
echo "startTime=$start_time"
echo "repository=$repository_root"
echo "outputDirectory=$output_directory"

image_sha256=$(sha256sum -- "$target_image" | awk '{print $1}')
annotation_sha256=$(sha256sum -- "$latest_truth_json" | awk '{print $1}')

set +e
uv run --project "$repository_root" python "$repository_root/tools/run_current_capture.py" \
  --label "$reference_annotation" \
  --reference-image "$reference_image" \
  --target-image "$target_image" \
  --config "$registration_config" \
  --out "$result_path"
detection_exit_code=$?

if [[ -f $result_path ]]; then
  uv run --project "$repository_root" python "$repository_root/tools/evaluate_current_capture.py" \
    --result "$result_path" \
    --target-image "$target_image" \
    --target-annotation "$latest_truth_json" \
    --expected-image-sha256 "$image_sha256" \
    --expected-annotation-sha256 "$annotation_sha256" \
    --out "$acceptance_path"
  acceptance_exit_code=$?
else
  echo "algorithm result missing; offline acceptance was not run" >&2
  acceptance_exit_code=2
fi

if [[ -f $acceptance_path ]]; then
  uv run --project "$repository_root" python - "$acceptance_path" "$metrics_path" "$metrics_text_path" <<'PY'
import json
import sys
from pathlib import Path

report_path, metrics_path, text_path = map(Path, sys.argv[1:])
report = json.loads(report_path.read_text(encoding="utf-8"))
d7 = report.get("metrics", {}).get("7")
phi = report.get("metrics", {}).get("Phi12.2")
d7_error = None if d7 is None else d7.get("lengthAbsoluteErrorPx")
phi_error = None if phi is None else phi.get("diameterAbsoluteErrorPx")
d7_pass = isinstance(d7_error, (int, float)) and d7_error <= 2.0
phi_pass = isinstance(phi_error, (int, float)) and phi_error <= 1.0
passed = report.get("status") == "evaluated" and d7_pass and phi_pass
metrics = {
    "schemaVersion": "hole2-latest-truth-key-metrics/1",
    "status": "PASS" if passed else "FAIL",
    "truthHashes": {
        "targetImage": report["hashes"]["targetImage"],
        "targetAnnotation": report["hashes"]["targetAnnotation"],
    },
    "registration": report["detectionSummary"]["registration"],
    "7": {
        "lengthAbsoluteErrorPx": d7_error,
        "maximumAllowedPx": 2.0,
        "passed": d7_pass,
        "metrics": d7,
    },
    "Phi12.2": {
        "diameterAbsoluteErrorPx": phi_error,
        "maximumAllowedPx": 1.0,
        "passed": phi_pass,
        "metrics": phi,
    },
    "evidenceScope": "single_image_pixel_geometry_only_no_production_ok_ng",
}
metrics_path.write_text(
    json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
    encoding="utf-8",
)
lines = [
    metrics["status"],
    f"7.lengthAbsoluteErrorPx={d7_error} limit=2.0 passed={d7_pass}",
    f"Phi12.2.diameterAbsoluteErrorPx={phi_error} limit=1.0 passed={phi_pass}",
    f"registrationValid={metrics['registration']['registrationValid']}",
    f"selectedOrientationDeg={metrics['registration']['selectedOrientationDeg']}",
]
text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
raise SystemExit(0 if passed else 2)
PY
  metrics_exit_code=$?
else
  echo "acceptance report missing; key metrics were not generated" >&2
  metrics_exit_code=2
fi
set -e

final_exit_code=0
if (( detection_exit_code != 0 || acceptance_exit_code != 0 || metrics_exit_code != 0 )); then
  final_exit_code=2
fi
end_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
printf '%s\n' "$final_exit_code" > "$exit_code_path"
printf '{\n  "startTime": "%s",\n  "endTime": "%s",\n  "detectionExitCode": %d,\n  "acceptanceExitCode": %d,\n  "metricsExitCode": %d,\n  "exitCode": %d\n}\n' \
  "$start_time" "$end_time" "$detection_exit_code" "$acceptance_exit_code" \
  "$metrics_exit_code" "$final_exit_code" > "$metadata_path"
echo "endTime=$end_time"
echo "exitCode=$final_exit_code"
echo "algorithmResult=$result_path"
echo "acceptanceReport=$acceptance_path"
echo "keyMetrics=$metrics_path"
exit "$final_exit_code"
