#!/usr/bin/env python3
"""Generate an independent D7 reference-profile audit outside formal output."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.hole_2.current_capture import (  # noqa: E402
    SimilarityTransform,
    load_authoritative_reference,
    load_registration_config,
    run_current_capture,
    sanitize_json_value,
    sha256_file,
)
from algorithms.hole_2.d7_reference_profile import (  # noqa: E402
    build_reference_profile_models,
    compare_audit_to_labelme,
    compare_formal_evidence_to_labelme,
    evaluate_reference_profile_candidate,
)
from algorithms.hole_2.main import load_gray  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-annotation", type=Path, required=True)
    parser.add_argument("--reference-image", type=Path, required=True)
    parser.add_argument("--target-image", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path,
        default=ROOT / "config" / "current_capture_registration.v1.json",
    )
    parser.add_argument("--target-labelme", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    # Formal detection is intentionally completed before optional truth is read.
    formal = run_current_capture(
        args.reference_annotation, args.reference_image,
        args.target_image, args.config,
    )
    reference = load_authoritative_reference(
        args.reference_annotation, args.reference_image
    )
    d7 = next(shape for shape in reference.shapes if shape.sanitized == "d7")
    if d7.line_p1 is None or d7.line_p2 is None:
        raise ValueError("authoritative D7 line is unavailable")
    transform_value = formal["authoritativeReference"].get("transform")
    if not formal["registration"]["registrationValid"] or not isinstance(transform_value, dict):
        audit = {
            "contractVersion": "d7-reference-profile-audit/1",
            "candidateValid": False,
            "failureReason": "registration_invalid",
            "formalMeasurementUpdated": False,
            "measurementTargetPx": None,
            "boundaryA": {}, "boundaryB": {}, "parallelismDeg": None,
        }
    else:
        transform = SimilarityTransform(
            float(transform_value["dx"]), float(transform_value["dy"]),
            float(transform_value["scale"]), float(transform_value["thetaDeg"]),
        )
        models = build_reference_profile_models(
            reference.gray, d7.line_p1, d7.line_p2
        )
        p1_target = transform.forward(*d7.line_p1)
        p2_target = transform.forward(*d7.line_p2)
        config = load_registration_config(args.config)
        d7_config = config["d7"]
        audit = evaluate_reference_profile_candidate(
            load_gray(args.target_image), models, p1_target, p2_target,
            target_scale=transform.scale,
            search_window_target_px=42.0,
            tangent_half_width_target_px=float(
                d7_config["paired_edge_strip_half_width_px"]
            ),
            tangent_samples=int(d7_config["paired_edge_strip_samples"]),
            min_support=int(d7_config["paired_edge_min_support"]),
            maximum_fit_residual_px=float(
                d7_config["max_fit_residual_target_px"]
            ),
            maximum_parallelism_deg=float(
                d7_config["max_boundary_parallelism_deg"]
            ),
        )
    formal_feature = formal["features"]["7"]
    report = {
        "reportVersion": "d7-reference-profile-diagnostic/1",
        "runtimeTruthUsed": False,
        "runtimeInputs": [
            {"role": "authoritative_reference_annotation", "path": str(args.reference_annotation), "sha256": sha256_file(args.reference_annotation)},
            {"role": "authoritative_reference_image", "path": str(args.reference_image), "sha256": sha256_file(args.reference_image)},
            {"role": "target_image", "path": str(args.target_image), "sha256": sha256_file(args.target_image)},
            {"role": "configuration", "path": str(args.config), "sha256": sha256_file(args.config)},
        ],
        "formalMeasurementSnapshot": {
            "measurementValid": formal_feature["measurementValid"],
            "failureReason": formal_feature["failureReason"],
            "sourceDetector": formal_feature["sourceDetector"],
            "lengthTargetPx": (
                None if formal_feature["target"] is None
                else formal_feature["target"]["lengthPx"]
            ),
        },
        "candidateAudit": audit,
        "truthComparison": None,
        "formalEvidenceTruthComparison": None,
    }
    if args.target_labelme is not None:
        # Offline evaluation happens only after the candidate has been frozen.
        report["truthComparison"] = compare_audit_to_labelme(
            audit, args.target_labelme
        )
        report["formalEvidenceTruthComparison"] = (
            compare_formal_evidence_to_labelme(
                formal_feature, args.target_labelme
            )
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(sanitize_json_value(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(args.output),
        "formalD7Valid": formal_feature["measurementValid"],
        "candidateValid": audit["candidateValid"],
        "candidateLengthTargetPx": audit["measurementTargetPx"],
        "truthCompared": args.target_labelme is not None,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
