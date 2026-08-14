#!/usr/bin/env python3
"""Build a path-safe physical outer-circle truth record from a reviewed LabelMe circle."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import inspect_image, safe_relative_path, sha256_file, write_json


TRUTH_LABEL = "physical_outer_circle_truth"


def build_truth(
    annotation_path: Path,
    image_root: Path,
    *,
    annotator: str,
    reviewer: str,
    truth_version: str,
) -> dict[str, Any]:
    if not annotator.strip() or not reviewer.strip() or annotator.strip() == reviewer.strip():
        raise ValueError("annotator and reviewer must be two distinct non-empty identities")
    if not truth_version.strip():
        raise ValueError("truth_version must be non-empty")
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    flags = payload.get("flags") or {}
    if flags.get("human_verified") is not True or flags.get("independent_from_algorithm") is not True:
        raise ValueError("LabelMe flags human_verified and independent_from_algorithm must both be true")
    matches = [
        shape for shape in payload.get("shapes", [])
        if shape.get("label") == TRUTH_LABEL and shape.get("shape_type") == "circle"
    ]
    if len(matches) != 1:
        raise ValueError(f"exactly one LabelMe circle labeled {TRUTH_LABEL!r} is required")
    points = matches[0].get("points") or []
    if len(points) != 2 or any(not isinstance(point, list) or len(point) != 2 for point in points):
        raise ValueError("LabelMe circle must contain center and circumference points")
    values = [float(value) for point in points for value in point]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("LabelMe circle points must be finite")
    center_x, center_y = map(float, points[0])
    edge_x, edge_y = map(float, points[1])
    radius = math.hypot(edge_x - center_x, edge_y - center_y)
    if radius <= 0.0:
        raise ValueError("LabelMe circle radius must be positive")

    relative_image = safe_relative_path(str(payload.get("imagePath", "")))
    image_path = (image_root.resolve() / relative_image).resolve()
    try:
        image_path.relative_to(image_root.resolve())
    except ValueError as exc:
        raise ValueError("LabelMe imagePath escapes image_root") from exc
    if not image_path.is_file():
        raise ValueError(f"LabelMe image does not exist under image_root: {relative_image.as_posix()}")
    image = inspect_image(image_path)
    if payload.get("imageWidth") != image["width"] or payload.get("imageHeight") != image["height"]:
        raise ValueError("LabelMe image dimensions do not match the referenced image")
    if not (0.0 <= center_x < image["width"] and 0.0 <= center_y < image["height"]):
        raise ValueError("LabelMe circle center lies outside the image")

    return {
        "schemaVersion": "physical-circle-truth/1",
        "truthVersion": truth_version.strip(),
        "status": "HUMAN_REVIEWED",
        "source": {
            "kind": "labelme_manual_circle",
            "label": TRUTH_LABEL,
            "annotator": annotator.strip(),
            "reviewer": reviewer.strip(),
            "independentFromAlgorithm": True,
            "annotationSha256": sha256_file(annotation_path),
        },
        "image": {
            "relativePath": relative_image.as_posix(),
            "sha256": image["sha256"],
            "width": image["width"],
            "height": image["height"],
            "format": image["format"],
        },
        "circle": {"centerX": center_x, "centerY": center_y, "radiusPx": radius},
        "limitations": [
            "A two-point LabelMe circle is an independently reviewed manual truth, not a metrology calibration.",
            "Formal sub-pixel accuracy still requires original BMP, calibrated scale and an approved annotation protocol.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotation", required=True, type=Path)
    parser.add_argument("--image-root", required=True, type=Path)
    parser.add_argument("--annotator", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--truth-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        truth = build_truth(
            args.annotation.resolve(), args.image_root.resolve(), annotator=args.annotator,
            reviewer=args.reviewer, truth_version=args.truth_version,
        )
        write_json(args.output.resolve(), truth)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.output}: status={truth['status']}, image={truth['image']['relativePath']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
