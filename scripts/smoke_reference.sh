#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
asset_dir=${HOLE2_ASSET_DIR:-/home/ubuntu/disk/gyj/HousingInspectionDemo/algorithms/hole_2}
output_dir=${HOLE2_SMOKE_OUTPUT:-"$project_root/outputs/reference-smoke"}

mkdir -p "$output_dir"
cd "$project_root"

uv run python algorithms/hole_2/main.py \
  --label "$asset_dir/annotation.json" \
  --reference-image "$asset_dir/reference.bmp" \
  --input-dir "$asset_dir" \
  --include-reference \
  --print-confirmed-features \
  --out "$output_dir/measurements.csv"

uv run python tools/evaluate_repeatability.py \
  --measurements "$output_dir/measurements.csv" \
  --config config/hole2_inspection.example.json \
  --output-dir "$output_dir/repeatability"

echo "Smoke outputs: $output_dir"
