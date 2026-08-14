"""Read-only adapter for the historical A-end-face circle/polar/notch core."""

from __future__ import annotations

import importlib.util
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from algorithms.slot_pose.angular_profile import assess_pairs, circular_delta_deg, extract_dark_candidates
from algorithms.slot_pose.contract import sha256_file, signed_relative_angle
from algorithms.slot_pose.role_assignment import assign_roles


REQUIRED_FUNCTIONS = (
    "robust_fit_circle",
    "object_bbox_center",
    "polar_resample",
    "find_outer_notch_angle",
    "estimate_rotation_by_notch",
    "estimate_rotation_by_polar",
    "estimate_global_transform",
    "build_reference_model",
    "load_detection_gray",
)


class LegacyAdapterError(RuntimeError):
    def __init__(self, code: str, stage: str, message: str, diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.diagnostics = diagnostics or {}


@dataclass(frozen=True)
class LegacyPaths:
    source: Path
    annotation: Path
    reference: Path


def _circular_difference_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


class LegacyAEndFaceAdapter:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        asset = config["legacy_asset"]
        self.paths = LegacyPaths(
            Path(asset["source_path"]).resolve(),
            Path(asset["annotation_path"]).resolve(),
            Path(asset["reference_path"]).resolve(),
        )
        self.expected_hashes = {
            self.paths.source: asset["source_sha256"],
            self.paths.annotation: asset["annotation_sha256"],
            self.paths.reference: asset["reference_sha256"],
        }
        self._verify_assets()
        self.module = self._load_module()
        self._verify_inventory()
        try:
            self.reference_model = self.module.build_reference_model(self.paths.annotation)
        except Exception as exc:
            raise LegacyAdapterError("FACE_NOT_FOUND", "reference_model", str(exc)) from exc
        resolved_reference = self.reference_model.reference_path.resolve()
        if resolved_reference != self.paths.reference:
            raise LegacyAdapterError(
                "ASSET_MISMATCH", "reference_model",
                f"annotation imagePath resolves to {resolved_reference}, expected {self.paths.reference}",
            )
        self._verify_assets()

    def _verify_assets(self) -> None:
        for path, expected in self.expected_hashes.items():
            if not path.is_file():
                raise LegacyAdapterError("ASSET_MISMATCH", "asset_verification", f"asset not found: {path}")
            actual = sha256_file(path)
            if actual != expected:
                raise LegacyAdapterError(
                    "ASSET_MISMATCH", "asset_verification",
                    f"SHA-256 mismatch for {path}: expected {expected}, actual {actual}",
                )

    def _load_module(self) -> ModuleType:
        module_name = f"slot_pose_legacy_a_end_face_{self.expected_hashes[self.paths.source][:16]}"
        spec = importlib.util.spec_from_file_location(module_name, self.paths.source)
        if spec is None or spec.loader is None:
            raise LegacyAdapterError("ASSET_MISMATCH", "asset_loading", "cannot create source module spec")
        module = importlib.util.module_from_spec(spec)
        prior = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            sys.modules.pop(module_name, None)
            raise LegacyAdapterError("ASSET_MISMATCH", "asset_loading", str(exc)) from exc
        finally:
            sys.dont_write_bytecode = prior
        return module

    def _verify_inventory(self) -> None:
        missing = [name for name in REQUIRED_FUNCTIONS if not callable(getattr(self.module, name, None))]
        if missing:
            raise LegacyAdapterError("ASSET_MISMATCH", "function_inventory", f"missing functions: {missing}")

    def _candidate_profile(
        self,
        gray: Any,
        center: tuple[float, float],
        outer_radius: float,
        shell_scale: float,
        label: str,
    ) -> dict[str, Any]:
        profile_config = self.config["detector"]["profile"]
        height, width = gray.shape
        if not all(math.isfinite(value) for value in (*center, outer_radius)) or outer_radius <= 0.0:
            raise LegacyAdapterError("FACE_NOT_FOUND", "face_quality", f"{label} center/radius is invalid")
        edge_clearance = min(center[0], center[1], width - 1.0 - center[0], height - 1.0 - center[1])
        shell_width = float(profile_config["shell_width_px"]) * float(shell_scale)
        profile_diagnostics = {
            "sampleCount": int(profile_config["n_angles"]),
            "radialSampleCount": int(profile_config["n_radii"]),
            "shellInnerRadiusPx": outer_radius - shell_width,
            "shellOuterRadiusPx": outer_radius,
            "completeRing": outer_radius <= edge_clearance,
        }
        if outer_radius > edge_clearance:
            raise LegacyAdapterError(
                "RING_TRUNCATED",
                "profile_extraction",
                f"{label} outer ring exceeds image boundary by {outer_radius - edge_clearance:.3f}px",
                {"angularProfile": profile_diagnostics},
            )
        if outer_radius - shell_width <= 0.0:
            raise LegacyAdapterError(
                "QUALITY_REJECTED", "profile_extraction", f"{label} shell width exceeds outer radius",
                {"angularProfile": profile_diagnostics},
            )
        polar = self.module.polar_resample(
            gray,
            center,
            outer_radius - shell_width,
            outer_radius,
            int(profile_config["n_radii"]),
            int(profile_config["n_angles"]),
        )
        candidates, summary = extract_dark_candidates(polar.mean(axis=0), profile_config)
        pairing_config = self.config["detector"].get("pairing")
        pairing = assess_pairs(candidates, pairing_config) if isinstance(pairing_config, dict) else None
        profile_diagnostics.update({
            "medianIntensity": summary["medianIntensity"],
            "madIntensity": summary["madIntensity"],
            "darkThreshold": summary["darkThreshold"],
        })
        return {
            "angularProfile": profile_diagnostics,
            "candidates": [candidate.to_dict() for candidate in candidates],
            "candidateSummary": summary,
            "pairing": pairing,
        }

    def estimate(self, image_path: Path) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            target_gray = self.module.load_detection_gray(image_path)
        except Exception as exc:
            raise LegacyAdapterError("INPUT_INVALID", "image_loading", str(exc)) from exc
        try:
            transform = self.module.estimate_global_transform(self.reference_model, target_gray)
        except Exception as exc:
            raise LegacyAdapterError("FACE_NOT_FOUND", "face_detection", str(exc)) from exc

        center = (float(transform.target_center[0]), float(transform.target_center[1]))
        scale = float(transform.scale)
        outer_radius = float(self.reference_model.alignment_outer_radius * scale)
        reference_notch = self.module.find_outer_notch_angle(
            self.reference_model.reference_gray,
            self.reference_model.alignment_center,
            self.reference_model.alignment_outer_radius,
        )
        if reference_notch is None:
            raise LegacyAdapterError("SLOT_NOT_FOUND", "reference_slot_detection", "historical reference has no notch")
        target_notch = self.module.find_outer_notch_angle(target_gray, center, outer_radius)
        if target_notch is None:
            raise LegacyAdapterError("SLOT_NOT_FOUND", "slot_detection", "historical notch detector returned no candidate")
        notch_angle, notch_half_width, notch_prominence = target_notch

        polar_rotation, polar_score = self.module.estimate_rotation_by_polar(
            self.reference_model.reference_gray,
            target_gray,
            self.reference_model.alignment_center,
            center,
            self.reference_model.alignment_inner_radius,
            self.reference_model.alignment_outer_radius,
            scale,
        )
        notch_rotation_result = self.module.estimate_rotation_by_notch(
            self.reference_model.reference_gray,
            target_gray,
            self.reference_model.alignment_center,
            center,
            self.reference_model.alignment_outer_radius,
            scale,
        )
        notch_rotation_deg = None
        notch_pair_prominence = None
        agreement_deg = None
        if notch_rotation_result is not None:
            notch_rotation_deg = math.degrees(float(notch_rotation_result[0]))
            notch_pair_prominence = float(notch_rotation_result[1])
            agreement_deg = _circular_difference_deg(math.degrees(float(polar_rotation)), notch_rotation_deg)

        detector = self.config["detector"]
        mode = str(detector.get("diagnostic_mode", "legacy_single_notch"))
        candidate_deg = math.degrees(float(notch_angle)) % 360.0
        failures: list[str] = []
        if float(polar_score) < float(detector["min_polar_score"]):
            failures.append("polar_score")
        if not float(detector["min_scale"]) <= scale <= float(detector["max_scale"]):
            failures.append("scale")

        diagnostics = {
            "diagnosticMode": mode,
            "candidateAzimuthImageDeg": candidate_deg,
            "referenceNotch": {
                "azimuthImageDeg": math.degrees(float(reference_notch[0])) % 360.0,
                "halfWidthDeg": math.degrees(float(reference_notch[1])),
                "prominence": float(reference_notch[2]),
            },
            "face": {
                "centerX": center[0], "centerY": center[1], "radiusPx": outer_radius,
                "scale": scale, "method": "legacy_estimate_global_transform",
            },
            "slot": {
                "halfWidthDeg": math.degrees(float(notch_half_width)),
                "prominence": float(notch_prominence),
                "notchPairProminence": notch_pair_prominence,
                "polarRotationDeg": math.degrees(float(polar_rotation)),
                "notchRotationDeg": notch_rotation_deg,
                "rotationAgreementDeg": agreement_deg,
            },
            "quality": {
                "polarScore": float(polar_score),
                "thresholds": detector,
                "failedChecks": failures,
            },
            "legacyMethod": str(transform.method),
            "elapsedMs": (time.perf_counter() - started) * 1000.0,
            "functionInventory": list(REQUIRED_FUNCTIONS),
        }
        if mode == "legacy_single_notch":
            if float(notch_prominence) < float(detector["min_notch_prominence"]):
                failures.append("notch_prominence")
            if agreement_deg is None:
                failures.append("notch_rotation_missing")
        elif mode == "paired_notches_centerline":
            try:
                reference_paired = self._candidate_profile(
                    self.reference_model.reference_gray,
                    self.reference_model.alignment_center,
                    float(self.reference_model.alignment_outer_radius),
                    1.0,
                    "reference",
                )
                target_paired = self._candidate_profile(target_gray, center, outer_radius, scale, "target")
            except LegacyAdapterError as exc:
                diagnostics.update(exc.diagnostics)
                exc.diagnostics = diagnostics
                raise
            diagnostics.update({
                "angularProfile": target_paired["angularProfile"],
                "candidates": target_paired["candidates"],
                "candidateSummary": target_paired["candidateSummary"],
                "pairing": target_paired["pairing"],
                "referencePairing": {
                    "candidateSummary": reference_paired["candidateSummary"],
                    "pairing": reference_paired["pairing"],
                },
            })
            reference_pair = reference_paired["pairing"]
            target_pair = target_paired["pairing"]
            if not reference_pair["unique"]:
                code = "SLOT_PAIR_AMBIGUOUS" if "pair_not_unique" in reference_pair["failedChecks"] else "SLOT_PAIR_NOT_FOUND"
                raise LegacyAdapterError(
                    code, "reference_pairing", f"reference notch pair failed: {reference_pair['failedChecks']}", diagnostics,
                )
            if not target_pair["unique"]:
                code = "SLOT_PAIR_AMBIGUOUS" if "pair_not_unique" in target_pair["failedChecks"] else "SLOT_PAIR_NOT_FOUND"
                raise LegacyAdapterError(
                    code, "slot_pairing", f"target notch pair failed: {target_pair['failedChecks']}", diagnostics,
                )
            candidate_deg = float(target_pair["centerlineDeg"])
            paired_rotation_deg = circular_delta_deg(candidate_deg, float(reference_pair["centerlineDeg"]))
            pair_agreement_deg = _circular_difference_deg(math.degrees(float(polar_rotation)), paired_rotation_deg)
            diagnostics["candidateAzimuthImageDeg"] = candidate_deg
            diagnostics["pairing"].update({
                "pairedRotationDeg": paired_rotation_deg,
                "polarPairAgreementDeg": pair_agreement_deg,
            })
            diagnostics["slot"].update({
                "pairedCenterlineDeg": candidate_deg,
                "pairedRotationDeg": paired_rotation_deg,
                "polarPairAgreementDeg": pair_agreement_deg,
            })
            if pair_agreement_deg > float(detector["max_polar_pair_disagreement_deg"]):
                raise LegacyAdapterError(
                    "SLOT_ROTATION_INCONSISTENT",
                    "quality_gate",
                    f"polar/paired disagreement {pair_agreement_deg:.3f}deg exceeds threshold",
                    diagnostics,
                )
        elif mode == "multi_notch_roles":
            try:
                target_roles = self._candidate_profile(target_gray, center, outer_radius, scale, "target")
            except LegacyAdapterError as exc:
                diagnostics.update(exc.diagnostics)
                exc.diagnostics = diagnostics
                raise
            role_assignment = assign_roles(
                [
                    _candidate_from_dict(item)
                    for item in target_roles["candidates"]
                ],
                detector["role_assignment"],
                expected_offset_deg=math.degrees(float(polar_rotation)),
            )
            diagnostics.update({
                "angularProfile": target_roles["angularProfile"],
                "candidates": target_roles["candidates"],
                "candidateSummary": target_roles["candidateSummary"],
                "roleAssignment": role_assignment,
                "drawingEvidence": {
                    "kind": "drawing_geometry_intent_only",
                    "label": "85°±5° (Z106)",
                    "provesA2FeatureMapping": False,
                },
            })
            if not role_assignment["unique"]:
                code = (
                    "ROLE_ASSIGNMENT_AMBIGUOUS"
                    if "role_assignment_not_unique" in role_assignment["failedChecks"]
                    else "ROLE_ASSIGNMENT_FAILED"
                )
                raise LegacyAdapterError(
                    code, "role_assignment",
                    f"notch role assignment failed: {role_assignment['failedChecks']}", diagnostics,
                )
            candidate_deg = float(role_assignment["selectedRoleAzimuthsDeg"]["target_left"])
            diagnostics["candidateAzimuthImageDeg"] = candidate_deg
            drawing_angle = role_assignment["drawingAngle"]
            pose = self.config["pose"]
            purpose = pose.get("output_purpose")
            if (
                purpose == "drawing_tolerance_inspection"
                and pose.get("drawing_datum_definition_confirmed")
                and pose.get("a2_drawing_feature_mapping_confirmed")
                and drawing_angle.get("drawingNominalDeg") is not None
                and drawing_angle.get("drawingToleranceDeg") is not None
            ):
                deviation = abs(float(drawing_angle["includedAngleDeg"]) - float(drawing_angle["drawingNominalDeg"]))
                drawing_angle["toleranceDeviationDeg"] = deviation
                drawing_angle["toleranceStatus"] = (
                    "PASS" if deviation <= float(drawing_angle["drawingToleranceDeg"]) else "FAIL"
                )
        else:  # load_config prevents this; retain a local guard for direct construction.
            raise LegacyAdapterError("QUALITY_REJECTED", "configuration", f"unsupported diagnostic mode: {mode}")

        self._verify_assets()
        if mode == "legacy_single_notch" and agreement_deg is not None and agreement_deg > float(detector["max_rotation_disagreement_deg"]):
            raise LegacyAdapterError(
                "SLOT_ROTATION_INCONSISTENT", "quality_gate",
                f"polar/notch disagreement {agreement_deg:.3f}deg exceeds threshold",
                diagnostics,
            )
        if failures:
            raise LegacyAdapterError(
                "QUALITY_REJECTED", "quality_gate", f"failed quality checks: {', '.join(failures)}", diagnostics,
            )

        if mode == "paired_notches_centerline":
            pairing = diagnostics["pairing"]
            confidence_parts = [
                min(1.0, float(polar_score) / max(1.0, 2.0 * float(detector["min_polar_score"]))),
                float(pairing["bestScore"]),
                min(1.0, float(pairing["scoreMargin"]) / max(1e-6, float(detector["pairing"]["min_score_margin"]))),
                max(0.0, 1.0 - float(pairing["polarPairAgreementDeg"]) / float(detector["max_polar_pair_disagreement_deg"])),
            ]
        elif mode == "multi_notch_roles":
            assignment = diagnostics["roleAssignment"]
            confidence_parts = [
                min(1.0, float(polar_score) / max(1.0, 2.0 * float(detector["min_polar_score"]))),
                float(assignment["bestScore"]),
                min(1.0, float(assignment["scoreMargin"]) / max(1e-6, float(detector["role_assignment"]["min_score_margin"]))),
            ]
        else:
            confidence_parts = [
                min(1.0, float(notch_prominence) / max(1.0, 2.0 * float(detector["min_notch_prominence"]))),
                min(1.0, float(polar_score) / max(1.0, 2.0 * float(detector["min_polar_score"]))),
                max(0.0, 1.0 - float(agreement_deg or 0.0) / max(1e-6, float(detector["max_rotation_disagreement_deg"]))),
            ]
        diagnostics["quality"]["confidenceComponents"] = confidence_parts
        diagnostics["quality"]["passed"] = True
        return {"candidate_image_deg": candidate_deg, "confidence": min(confidence_parts), "diagnostics": diagnostics}

    def mechanical_angle(self, candidate_image_deg: float) -> float:
        pose = self.config["pose"]
        if self.config["detector"].get("diagnostic_mode") == "multi_notch_roles":
            if not pose.get("drawing_datum_definition_confirmed"):
                raise LegacyAdapterError(
                    "DATUM_DEFINITION_UNCONFIRMED", "pose_mapping",
                    "drawing datum definition has not been confirmed",
                )
            if not pose.get("a2_drawing_feature_mapping_confirmed"):
                raise LegacyAdapterError(
                    "FEATURE_MAPPING_UNCONFIRMED", "pose_mapping",
                    "A2 image candidates have not been mapped to drawing datum/target features",
                )
            if pose.get("output_purpose") != "mechanical_correction":
                raise LegacyAdapterError(
                    "OUTPUT_PURPOSE_UNCONFIRMED", "pose_mapping",
                    "drawing tolerance observation is not a confirmed mechanical correction contract",
                )
        if not pose.get("target_semantics_confirmed"):
            raise LegacyAdapterError(
                "TARGET_SEMANTICS_UNCONFIRMED", "pose_mapping",
                "diagnostic target has not been confirmed as the production mechanical target",
            )
        if not pose.get("conventions_confirmed"):
            raise LegacyAdapterError(
                "POSE_CONVENTION_UNCONFIRMED", "pose_mapping",
                "mechanical zero and positive direction are not confirmed",
            )
        zero = pose.get("mechanical_zero_image_deg")
        direction = pose.get("positive_direction")
        if zero is None or direction not in {"cw", "ccw"}:
            raise LegacyAdapterError("POSE_CONVENTION_UNCONFIRMED", "pose_mapping", "pose convention is incomplete")
        angle = signed_relative_angle(candidate_image_deg, float(zero), str(direction))
        valid_range = pose.get("valid_range_deg")
        if valid_range is not None and not float(valid_range[0]) <= angle <= float(valid_range[1]):
            raise LegacyAdapterError("ANGLE_OUT_OF_RANGE", "pose_mapping", f"angle {angle:.6f}deg is outside valid range")
        return angle


def _candidate_from_dict(payload: dict[str, Any]):
    from algorithms.slot_pose.angular_profile import NotchCandidate

    return NotchCandidate(
        candidate_id=str(payload["candidateId"]),
        center_deg=float(payload["centerDeg"]),
        half_width_deg=float(payload["halfWidthDeg"]),
        start_deg=float(payload["startDeg"]),
        end_deg=float(payload["endDeg"]),
        wraps_boundary=bool(payload["wrapsBoundary"]),
        prominence=float(payload["prominence"]),
        deficit_area=float(payload["deficitArea"]),
        rank=int(payload["rank"]),
    )
