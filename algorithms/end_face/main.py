#!/usr/bin/env python3
"""Run the preserved desktop A-end-face detector for one image and emit JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.end_face import core
from algorithms.end_face.contract import failure_result, success_result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotation", required=True, type=Path, help="LabelMe JSON whose imagePath points to the reference image.")
    parser.add_argument("--image", required=True, type=Path, help="Target A-end-face image.")
    parser.add_argument("--output", default="-", help="Result JSON path, or '-' for stdout.")
    parser.add_argument("--pixel-size", type=float, default=1.0, help="Physical units per pixel; 1 keeps pixel units.")
    parser.add_argument("--task-id", help="Caller correlation id; defaults to the input image hash prefix.")
    parser.add_argument("--strict", action="store_true", help="Return exit code 1 for failed or invalid measurements.")
    return parser.parse_args(argv)


def run(image: Path, annotation: Path, pixel_size: float = 1.0, task_id: str | None = None) -> dict:
    image = image.resolve()
    annotation = annotation.resolve()
    resolved_task_id = task_id or f"end-face:{image.stem}"
    try:
        if pixel_size <= 0:
            raise ValueError("pixel-size must be greater than zero")
        if not image.is_file():
            raise FileNotFoundError(f"input image does not exist: {image}")
        if not annotation.is_file():
            raise FileNotFoundError(f"annotation does not exist: {annotation}")
        reference_model = core.build_reference_model(annotation)
        measurements, shift_method = core.detect_measurements(reference_model, image, pixel_size)
        return success_result(
            task_id=resolved_task_id,
            image=image,
            annotation=annotation,
            reference=reference_model.reference_path,
            pixel_size=pixel_size,
            shift_method=shift_method,
            measurements=measurements,
        )
    except Exception as exc:
        return failure_result(task_id=resolved_task_id, image=image, annotation=annotation, error=exc)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = run(args.image, args.annotation, args.pixel_size, args.task_id)
        content = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output == "-":
            print(content, end="")
        else:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content, encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    result = payload.get("result") or {}
    valid = payload.get("technicalStatus") == "succeeded" and bool(result.get("valid"))
    return 1 if args.strict and not valid else 0


if __name__ == "__main__":
    raise SystemExit(main())
