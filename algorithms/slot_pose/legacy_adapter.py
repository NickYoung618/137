"""Read-only adapter for the historical A-end-face circle/polar/notch core."""

from __future__ import annotations

import importlib
import importlib.util
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

from algorithms.slot_pose.angular_profile import assess_pairs, circular_delta_deg, extract_dark_candidates
from algorithms.slot_pose.circle_edge_candidates import (
    load_detection_gray_fast, outer_boundary_edge_candidates,
)
from algorithms.slot_pose.contract import (
    BUNDLED_LEGACY_MODULE,
    sha256_file,
    signed_relative_angle,
)
from algorithms.slot_pose.full_frame_circle_locator import locate_full_frame_circle
from algorithms.slot_pose.fixture_shadow import (
    analyze_fixture_shadows,
    build_fixture_overlap_evaluation_candidates,
)
from algorithms.slot_pose.groove_recognition import provisional_candidate_ids, recognize_grooves
from algorithms.slot_pose.groove_refinement import refine_groove_opening
from algorithms.slot_pose.groove_resolution import resolve_groove_candidates
from algorithms.slot_pose.groove_shadow_geometry import (
    assess_candidate_fixture_overlap,
    assess_groove_floor_evidence,
    build_fixture_source_exclusion,
    detect_stationary_fixture_sectors,
)
from algorithms.slot_pose.groove_shadow_discrimination import (
    build_candidate_source_evidence,
    classify_groove_shadow_sources,
)
from algorithms.slot_pose.physical_outer_circle import locate_physical_outer_circle
from algorithms.slot_pose.polar_quality_adjudication import adjudicate_polar_quality
from algorithms.slot_pose.role_assignment import assign_roles
from algorithms.slot_pose.single_groove_pose import build_single_groove_pose
from algorithms.slot_pose.sidewall_consistency import assess_sidewall_source_consistency
from algorithms.slot_pose.sidewall_consistency_candidate import assess_sidewall_consistency_candidate
from algorithms.slot_pose.source_consistency_adjudication import adjudicate_source_consistency
from algorithms.slot_pose.local_second_wall import diagnose_local_second_wall


REQUIRED_FUNCTIONS = (
    "robust_fit_circle",
    "outer_boundary_edge_point",
    "bilinear_sample",
    "parabolic_peak",
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


def wall_family_recovery_used(refinement: dict[str, Any]) -> bool:
    """Recognize supported recovery evidence without coupling safety to one version."""
    return any(
        isinstance(refinement.get(side_name), dict)
        and (
            refinement[side_name].get("wallFamilyRecoveryUsed") is True
            or refinement[side_name].get("lineFitStrategy") in {
                "bounded-cross-radius-wall-family-v1",
                "shared-longitudinal-wall-family-v2",
            }
        )
        for side_name in ("startSide", "endSide")
    )


def recovery_fixture_exclusion_verified(evidence: dict[str, Any] | None) -> bool:
    """Require the complete fixture/U-contour proof for every recovery path."""
    return bool(
        isinstance(evidence, dict)
        and evidence.get("schemaVersion") in {
            "fixture-groove-source-exclusion/1",
            "fixture-groove-source-exclusion/2",
            "fixture-groove-source-exclusion/4",
        }
        and evidence.get("status") == "verified"
        and evidence.get("fixtureBodiesVerified") is True
        and evidence.get("uContourComplete") is True
        and evidence.get("fixtureSourceExcluded") is True
        and evidence.get("candidateSelectionUsedFixedAngle") is False
        and (
            evidence.get("schemaVersion") != "fixture-groove-source-exclusion/4"
            or (
                evidence.get("radialUContourOwnershipVerified") is True
                and evidence.get("manualTruthAppliedAtRuntime") is False
            )
        )
    )


def apply_polar_quality_adjudication(
    diagnostics: dict[str, Any],
    original_failures: list[str],
    config: dict[str, Any] | None,
) -> list[str]:
    """Attach an independent decision and return a new effective failure list."""
    evidence = {
        key: diagnostics.get(key)
        for key in (
            "quality", "physicalOuterCircle", "grooveRecognition",
            "grooveRefinement", "singleGroovePose",
        )
    }
    decision = adjudicate_polar_quality(evidence, config)
    if decision is None:
        return list(original_failures)
    diagnostics["polarQualityAdjudication"] = decision
    return list(decision["effectiveFailedChecks"])


@dataclass(frozen=True)
class LegacyPaths:
    source: Path
    annotation: Path
    reference: Path


def _circular_difference_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def apply_normalized_face_search_roi(gray: np.ndarray, roi: list[float]) -> np.ndarray:
    """Mask alignment distractors while preserving original image coordinates."""
    height, width = gray.shape
    x_min, y_min, x_max, y_max = map(float, roi)
    left = max(0, min(width, int(math.floor(x_min * width))))
    top = max(0, min(height, int(math.floor(y_min * height))))
    right = max(0, min(width, int(math.ceil(x_max * width))))
    bottom = max(0, min(height, int(math.ceil(y_max * height))))
    masked = np.zeros_like(gray)
    masked[top:bottom, left:right] = gray[top:bottom, left:right]
    return masked


class LegacyAEndFaceAdapter:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        asset = config["legacy_asset"]
        self.source_mode = str(asset.get("source_mode", "external_file"))
        source_path = self._resolve_source_path(asset)
        self.paths = LegacyPaths(
            source_path,
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
        self.function_inventory = REQUIRED_FUNCTIONS
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

    def _resolve_source_path(self, asset: dict[str, Any]) -> Path:
        if self.source_mode == "external_file":
            source = asset.get("source_path")
            if not isinstance(source, str) or not source.strip():
                raise LegacyAdapterError(
                    "ASSET_MISMATCH",
                    "asset_verification",
                    "legacy_asset.source_path is required for external_file mode",
                )
            return Path(source).resolve()
        if self.source_mode != "bundled_module":
            raise LegacyAdapterError(
                "ASSET_MISMATCH",
                "asset_verification",
                f"unsupported legacy source mode: {self.source_mode}",
            )
        module_name = asset.get("bundled_module")
        if module_name != BUNDLED_LEGACY_MODULE:
            raise LegacyAdapterError(
                "ASSET_MISMATCH",
                "asset_verification",
                f"bundled module must be {BUNDLED_LEGACY_MODULE}",
            )
        spec = importlib.util.find_spec(BUNDLED_LEGACY_MODULE)
        if spec is None or not spec.origin:
            raise LegacyAdapterError(
                "ASSET_MISMATCH",
                "asset_loading",
                f"cannot resolve bundled module: {BUNDLED_LEGACY_MODULE}",
            )
        return Path(spec.origin).resolve()

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

    def verify_assets(self) -> None:
        """Recheck locked assets for long-lived batch adapters."""
        self._verify_assets()

    def _load_module(self) -> ModuleType:
        if self.source_mode == "bundled_module":
            try:
                module = importlib.import_module(BUNDLED_LEGACY_MODULE)
            except Exception as exc:
                raise LegacyAdapterError(
                    "ASSET_MISMATCH", "asset_loading", str(exc)
                ) from exc
            origin = Path(str(getattr(module, "__file__", ""))).resolve()
            if origin != self.paths.source:
                raise LegacyAdapterError(
                    "ASSET_MISMATCH",
                    "asset_loading",
                    f"bundled module resolved to {origin}, expected {self.paths.source}",
                )
            return module
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
        family_enabled = bool(
            self.config.get("detector", {}).get("physical_outer_circle", {})
            .get("edge_family_selection", {}).get("enabled", False)
        )
        if family_enabled and self.source_mode != "bundled_module":
            missing.append("bundled_module_required_for_edge_family_selection")
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
        one_dimensional_profile = polar.mean(axis=0)
        candidates, summary = extract_dark_candidates(
            one_dimensional_profile,
            profile_config,
            self.config["detector"].get("dark_candidate_robustness"),
        )
        raw_candidates = [candidate.to_dict() for candidate in candidates]
        fixture_evidence = analyze_fixture_shadows(
            one_dimensional_profile,
            raw_candidates,
            self.config["detector"].get("fixture_shadow_model"),
        )
        residual_candidates = list(fixture_evidence["residualCandidates"])
        evaluation_view = build_fixture_overlap_evaluation_candidates(
            raw_candidates, fixture_evidence,
        )
        evaluation_candidates = evaluation_view["candidates"]
        pairing_config = self.config["detector"].get("pairing")
        pairing = assess_pairs(candidates, pairing_config) if isinstance(pairing_config, dict) else None
        profile_diagnostics.update({
            "medianIntensity": summary["medianIntensity"],
            "madIntensity": summary["madIntensity"],
            "darkThreshold": summary["darkThreshold"],
            "rawDarkThreshold": summary["rawDarkThreshold"],
            "thresholdUsable": summary["thresholdUsable"],
            "thresholdMode": summary["thresholdMode"],
            "thresholdHypotheses": summary["thresholdHypotheses"],
        })
        return {
            "angularProfile": profile_diagnostics,
            "candidates": raw_candidates,
            "evaluationCandidates": evaluation_candidates,
            "decompositionCandidates": residual_candidates,
            "fixtureShadowEvidence": fixture_evidence,
            "fixtureOverlapEvaluation": {
                key: value for key, value in evaluation_view.items() if key != "candidates"
            },
            "candidateSummary": summary,
            "pairing": pairing,
        }

    def _recognize_target_grooves(
        self,
        gray: Any,
        center: tuple[float, float],
        outer_radius: float,
        scale: float,
        raw_candidates: list[dict[str, Any]],
        minimum_required_count: int,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        config = self.config["detector"]["groove_recognition"]
        radial_span = float(config["radial_span_px"]) * scale
        inner_radius = outer_radius - radial_span
        if inner_radius <= 0.0:
            raise LegacyAdapterError(
                "GROOVE_RECOGNITION_FAILED", "groove_recognition",
                "groove recognition radial span exceeds the located face radius",
            )
        polar = self.module.polar_resample(
            gray, center, inner_radius, outer_radius,
            int(config["n_radii"]), int(self.config["detector"]["profile"]["n_angles"]),
        )
        candidate_objects = [_candidate_from_dict(item) for item in raw_candidates]
        recognition = recognize_grooves(
            polar, candidate_objects, outer_radius, radial_span, config,
            minimum_required_count, pixel_scale=scale,
        )
        by_id = {item["candidateId"]: item for item in recognition["assessments"]}
        recovery_config = self.config["detector"].get("groove_recognition_recovery")
        provisional_ids = provisional_candidate_ids(
            recognition["assessments"], recovery_config,
        )
        if recovery_config is not None:
            recognition["provisionalCandidateIds"] = provisional_ids
            recognition["effectiveCandidateIds"] = sorted(set(
                recognition["acceptedCandidateIds"] + provisional_ids
            ))
        accepted: list[dict[str, Any]] = []
        for raw in raw_candidates:
            assessment = by_id[raw["candidateId"]]
            if assessment["accepted"] or raw["candidateId"] in provisional_ids:
                accepted.append({**raw, **assessment})
                if recovery_config is not None:
                    accepted[-1]["provisionalRecognition"] = (
                        raw["candidateId"] in provisional_ids
                    )
        return recognition, accepted

    def estimate(self, image_path: Path) -> dict[str, Any]:
        started = time.perf_counter()
        detector = self.config["detector"]
        family_enabled = bool(
            detector.get("physical_outer_circle", {})
            .get("edge_family_selection", {}).get("enabled", False)
        )
        try:
            target_gray = (
                load_detection_gray_fast(image_path)
                if family_enabled else self.module.load_detection_gray(image_path)
            )
        except Exception as exc:
            raise LegacyAdapterError("INPUT_INVALID", "image_loading", str(exc)) from exc
        mode = str(detector.get("diagnostic_mode", "legacy_single_notch"))
        face_search_roi = detector.get("face_search_roi_normalized")
        locator_config = detector.get("full_frame_circle_locator") or {}
        locator_enabled = mode == "single_real_groove" and bool(locator_config.get("enabled", False))
        transform = None
        prelocated_physical: dict[str, Any] | None = None
        circle_localization: dict[str, Any] | None = None
        if locator_enabled:
            outer_model = next(
                (
                    model for model in self.reference_model.shapes
                    if model.label == self.reference_model.outer_label and model.circle is not None
                ),
                None,
            )
            if outer_model is None:
                raise LegacyAdapterError(
                    "PHYSICAL_OUTER_CIRCLE_FAILED", "physical_outer_circle",
                    "locked reference model has no physical outer-circle anchor",
                )
            circle_localization = locate_full_frame_circle(
                target_gray,
                (float(outer_model.circle[0]), float(outer_model.circle[1]), float(outer_model.circle[2])),
                self.module.outer_boundary_edge_point,
                self.module.robust_fit_circle,
                locator_config,
                final_physical_config=detector.get("physical_outer_circle"),
                source_sha256=self.expected_hashes[self.paths.source],
                outer_boundary_edge_candidates=(outer_boundary_edge_candidates if family_enabled else None),
            )
            if circle_localization["status"] != "accepted":
                if circle_localization["status"] in {"ambiguous", "overflow"}:
                    code = "HOUSING_CIRCLE_AMBIGUOUS"
                elif circle_localization["status"] == "refinement_failed":
                    code = "PHYSICAL_OUTER_CIRCLE_FAILED"
                else:
                    code = "HOUSING_CIRCLE_NOT_FOUND"
                raise LegacyAdapterError(
                    code,
                    "circle_localization",
                    f"full-frame housing circle localization failed: {circle_localization['failedChecks']}",
                    {"diagnosticMode": mode, "circleLocalization": circle_localization},
                )
            physical_circle = circle_localization["finalPhysicalCircle"]
            assert physical_circle is not None
            center = (float(physical_circle["centerX"]), float(physical_circle["centerY"]))
            scale = float(physical_circle["radiusPx"]) / float(outer_model.circle[2])
            outer_radius = float(self.reference_model.alignment_outer_radius * scale)
            prelocated_physical = circle_localization["finalPhysicalCircleDiagnostics"]
        else:
            try:
                alignment_gray = (
                    apply_normalized_face_search_roi(target_gray, face_search_roi)
                    if isinstance(face_search_roi, list)
                    else target_gray
                )
                transform = self.module.estimate_global_transform(self.reference_model, alignment_gray)
            except Exception as exc:
                raise LegacyAdapterError("FACE_NOT_FOUND", "face_detection", str(exc)) from exc
            center = (float(transform.target_center[0]), float(transform.target_center[1]))
            scale = float(transform.scale)
            outer_radius = float(self.reference_model.alignment_outer_radius * scale)

        # The historical single-notch detector is a legacy-mode baseline, not a
        # prerequisite for profile-based paired or generic multi-role modes.
        reference_notch = None
        target_notch = None
        notch_angle = None
        notch_half_width = None
        notch_prominence = None
        if mode == "legacy_single_notch":
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
        notch_rotation_result = None
        if mode == "legacy_single_notch":
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

        candidate_deg = math.degrees(float(notch_angle)) % 360.0 if notch_angle is not None else None
        failures: list[str] = []
        if float(polar_score) < float(detector["min_polar_score"]):
            failures.append("polar_score")
        if not float(detector["min_scale"]) <= scale <= float(detector["max_scale"]):
            failures.append("scale")

        diagnostics = {
            "diagnosticMode": mode,
            "candidateAzimuthImageDeg": candidate_deg,
            "referenceNotch": None if reference_notch is None else {
                "azimuthImageDeg": math.degrees(float(reference_notch[0])) % 360.0,
                "halfWidthDeg": math.degrees(float(reference_notch[1])),
                "prominence": float(reference_notch[2]),
            },
            "face": {
                "centerX": center[0], "centerY": center[1], "radiusPx": outer_radius,
                "scale": scale,
                "method": "full_frame_circle_locator" if locator_enabled else "legacy_estimate_global_transform",
                "searchRoiNormalized": face_search_roi,
            },
            "slot": {
                "halfWidthDeg": math.degrees(float(notch_half_width)) if notch_half_width is not None else None,
                "prominence": float(notch_prominence) if notch_prominence is not None else None,
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
            "legacyMethod": "full_frame_circle_locator" if locator_enabled else str(transform.method),
            "elapsedMs": (time.perf_counter() - started) * 1000.0,
            "functionInventory": list(REQUIRED_FUNCTIONS),
            "legacyCoreSource": {
                "mode": self.source_mode,
                "module": (
                    BUNDLED_LEGACY_MODULE
                    if self.source_mode == "bundled_module"
                    else None
                ),
                "sourceSha256": self.expected_hashes[self.paths.source],
                "upstreamSourceSha256": self.config["legacy_asset"].get(
                    "upstream_source_sha256"
                ),
                "repositoryContained": self.source_mode == "bundled_module",
            },
        }
        if circle_localization is not None:
            diagnostics["circleLocalization"] = circle_localization
        if mode == "legacy_single_notch":
            assert notch_prominence is not None
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
        elif mode in {"multi_notch_roles", "single_real_groove"}:
            outer_model = next(
                (
                    model for model in self.reference_model.shapes
                    if model.label == self.reference_model.outer_label and model.circle is not None
                ),
                None,
            )
            if outer_model is None:
                raise LegacyAdapterError(
                    "PHYSICAL_OUTER_CIRCLE_FAILED", "physical_outer_circle",
                    "locked reference model has no physical outer-circle anchor", diagnostics,
                )
            if prelocated_physical is not None:
                physical_outer = prelocated_physical
            else:
                assert transform is not None
                search_center = transform.apply_point((outer_model.circle[0], outer_model.circle[1]))
                search_radius = transform.apply_radius(outer_model.circle[2])
                physical_outer = locate_physical_outer_circle(
                    target_gray,
                    center,
                    outer_radius,
                    (float(search_center[0]), float(search_center[1])),
                    float(search_radius),
                    self.module.outer_boundary_edge_point,
                    self.module.robust_fit_circle,
                    detector.get("physical_outer_circle"),
                    source_sha256=self.expected_hashes[self.paths.source],
                    pixel_scale=scale,
                    outer_boundary_edge_candidates=(outer_boundary_edge_candidates if family_enabled else None),
                )
            diagnostics["physicalOuterCircle"] = physical_outer
            if physical_outer["status"] != "accepted":
                shadow_source_config = detector.get(
                    "groove_shadow_source_discrimination", {"enabled": False}
                )
                if mode == "single_real_groove" and shadow_source_config["enabled"]:
                    diagnostics["grooveShadowSourceDiscrimination"] = (
                        classify_groove_shadow_sources(
                            [], enabled=True, upstream_accepted=False,
                            polar_quality_accepted="polar_score" not in failures,
                            existing_pose_chain_allowed=False,
                            terminal_stage="upstream_outer_circle",
                            strategy_version=shadow_source_config["strategy_version"],
                        )
                    )
                code = (
                    "HOUSING_CIRCLE_AMBIGUOUS"
                    if "ambiguous_edge_families" in (physical_outer.get("failedChecks") or [])
                    else "PHYSICAL_OUTER_CIRCLE_FAILED"
                )
                raise LegacyAdapterError(
                    code, "physical_outer_circle",
                    f"physical outer circle failed: {physical_outer['failedChecks']}", diagnostics,
                )
            physical = physical_outer["physicalCircle"]
            assert physical is not None
            groove_center = (float(physical["centerX"]), float(physical["centerY"]))
            groove_outer_radius = float(physical["radiusPx"])
            fixture_geometry_enabled = bool(
                (
                    detector.get("groove_shadow_source_discrimination", {}).get("enabled", False)
                    and detector.get("groove_shadow_source_discrimination", {}).get("schema_version")
                    == "groove-shadow-source-discrimination/2"
                )
                or detector.get("groove_recognition_recovery", {}).get("enabled", False)
                or detector.get("groove_refinement", {}).get("wall_edge_family", {}).get(
                    "enabled", False
                )
                or (
                    detector.get("source_consistency_adjudication", {}).get("enabled", False)
                    and detector.get("source_consistency_adjudication", {}).get("schema_version")
                    in {
                        "source-consistency-adjudication/2",
                        "source-consistency-adjudication/5",
                    }
                )
            )
            fixture_body_evidence = (
                detect_stationary_fixture_sectors(
                    target_gray, groove_center, groove_outer_radius,
                )
                if mode == "single_real_groove" and fixture_geometry_enabled
                else None
            )
            if fixture_body_evidence is not None:
                diagnostics["stationaryFixtureGeometry"] = fixture_body_evidence
            try:
                target_roles = self._candidate_profile(
                    target_gray, groove_center, groove_outer_radius, scale, "target physical outer circle",
                )
            except LegacyAdapterError as exc:
                diagnostics.update(exc.diagnostics)
                shadow_source_config = detector.get(
                    "groove_shadow_source_discrimination", {"enabled": False}
                )
                if mode == "single_real_groove" and shadow_source_config["enabled"]:
                    diagnostics["grooveShadowSourceDiscrimination"] = (
                        classify_groove_shadow_sources(
                            [], enabled=True, upstream_accepted=True,
                            polar_quality_accepted="polar_score" not in failures,
                            existing_pose_chain_allowed=False,
                            terminal_stage="candidate_generation",
                            strategy_version=shadow_source_config["strategy_version"],
                        )
                    )
                exc.diagnostics = diagnostics
                raise
            minimum_required = (
                1 if mode == "single_real_groove"
                else len(detector["role_assignment"]["assignments"])
            )
            recognition, groove_candidates = self._recognize_target_grooves(
                target_gray, groove_center, groove_outer_radius, scale,
                target_roles["evaluationCandidates"], minimum_required,
            )
            fixture_candidate_screening = None
            if isinstance(fixture_body_evidence, dict):
                assessment_by_id = {
                    item["candidateId"]: item
                    for item in recognition.get("assessments", [])
                    if isinstance(item, dict) and isinstance(item.get("candidateId"), str)
                }
                screening_items = []
                for raw in target_roles["evaluationCandidates"][:16]:
                    assessment = assessment_by_id.get(raw.get("candidateId"), {})
                    candidate_evidence = {**raw, **assessment}
                    overlap = assess_candidate_fixture_overlap(
                        candidate_evidence, fixture_body_evidence,
                    )
                    floor = assess_groove_floor_evidence(
                        target_gray, groove_center, groove_outer_radius,
                        candidate_evidence, self.module.bilinear_sample,
                        pixel_scale=scale,
                        search_depth_px=float(
                            detector["groove_recognition"]["radial_span_px"]
                        ) * scale,
                    )
                    role = overlap.get("overlapRole")
                    if role == "lower_fixture":
                        disposition = "LOWER_FIXTURE_FALSE_SOURCE"
                    elif role in {"upper_fixture", "multiple_fixture_bodies"} and floor.get("status") == "accepted":
                        disposition = "UPPER_FIXTURE_OVERLAP_WITH_FLOOR_EVIDENCE"
                    elif role in {"upper_fixture", "multiple_fixture_bodies"}:
                        disposition = "UPPER_FIXTURE_MIXED_OR_OCCLUDED_RISK"
                    elif floor.get("status") == "accepted":
                        disposition = "NONFIXTURE_U_FLOOR_EVIDENCE"
                    else:
                        disposition = "INSUFFICIENT_SOURCE_EVIDENCE"
                    screening_items.append({
                        "candidateId": raw.get("candidateId"),
                        "originalRecognitionAccepted": assessment.get("accepted") is True,
                        "originalRecognitionFailedChecks": list(
                            assessment.get("rejectionReasons") or []
                        ),
                        "overlap": overlap, "floor": floor,
                        "disposition": disposition,
                    })
                fixture_candidate_screening = {
                    "schemaVersion": "fixture-candidate-source-screening/1",
                    "status": "evaluated",
                    "candidateCount": len(screening_items),
                    "candidates": screening_items,
                    "lowerFixtureFalseSourceCount": sum(
                        item["disposition"] == "LOWER_FIXTURE_FALSE_SOURCE"
                        for item in screening_items
                    ),
                    "upperFixtureMixedOrOccludedRiskCount": sum(
                        item["disposition"] == "UPPER_FIXTURE_MIXED_OR_OCCLUDED_RISK"
                        for item in screening_items
                    ),
                    "candidateSelectionUsedFixedAngle": False,
                    "manualTruthAppliedAtRuntime": False,
                }
            diagnostics.update({
                "angularProfile": target_roles["angularProfile"],
                "candidates": target_roles["candidates"],
                "rawCandidates": target_roles["candidates"],
                "decompositionCandidates": target_roles["decompositionCandidates"],
                "fixtureShadowEvidence": target_roles["fixtureShadowEvidence"],
                "fixtureOverlapEvaluation": target_roles["fixtureOverlapEvaluation"],
                "candidateSummary": target_roles["candidateSummary"],
                "grooveRecognition": recognition,
                "grooveCandidates": groove_candidates,
                "drawingEvidence": {
                    "kind": "drawing_geometry_intent_only",
                    "label": "85°±5° (Z106)",
                    "provesA2FeatureMapping": False,
                },
            })
            if fixture_candidate_screening is not None:
                diagnostics["fixtureCandidateSourceScreening"] = fixture_candidate_screening
            if mode == "single_real_groove":
                pose_config = detector["single_groove_pose"]
                is_refined = pose_config["schema_version"] in {
                    "single-real-groove-pose-config/2", "single-real-groove-pose-config/3",
                }
                pose_recognition_status = recognition["status"]
                def refine_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
                    refinement = refine_groove_opening(
                        target_gray,
                        groove_center,
                        groove_outer_radius,
                        candidate,
                        self.module.bilinear_sample,
                        self.module.parabolic_peak,
                        detector["groove_refinement"],
                        pixel_scale=scale,
                    )
                    source_consistency = assess_sidewall_source_consistency(
                        refinement,
                        detector.get("sidewall_source_consistency"),
                    )
                    fixture_source_exclusion = (
                        build_fixture_source_exclusion(
                            candidate, fixture_body_evidence, refinement,
                            groove_floor_evidence=assess_groove_floor_evidence(
                                target_gray, groove_center, groove_outer_radius,
                                candidate, self.module.bilinear_sample,
                                pixel_scale=scale,
                            ),
                            source_consistency_evidence=source_consistency,
                            radial_envelope_extra_deg=(
                                detector["groove_refinement"][
                                    "max_intersection_coarse_delta_deg"
                                ]
                                if detector.get("source_consistency_adjudication", {}).get(
                                    "enabled"
                                ) is True
                                and detector.get("source_consistency_adjudication", {}).get(
                                    "schema_version"
                                ) == "source-consistency-adjudication/5"
                                else None
                            ),
                        )
                        if isinstance(fixture_body_evidence, dict) else None
                    )
                    output = {**refinement, "sourceConsistency": source_consistency}
                    if fixture_source_exclusion is not None:
                        output["fixtureSourceExclusion"] = fixture_source_exclusion
                    source_candidate = assess_sidewall_consistency_candidate(
                        source_consistency,
                        detector.get("sidewall_source_consistency_candidate"),
                    )
                    if source_candidate is not None:
                        output["sourceConsistencyCandidate"] = source_candidate
                    source_adjudication = adjudicate_source_consistency(
                        source_consistency,
                        detector.get("source_consistency_adjudication"),
                        fixture_source_evidence=(
                            {
                                key: fixture_source_exclusion[key]
                                for key in (
                                    "schemaVersion", "status", "fixtureBodiesVerified",
                                    "uContourComplete", "fixtureSourceExcluded",
                                    "candidateSelectionUsedFixedAngle",
                                    "radialSidewallsVerified", "radialRecoveryApplied",
                                    "twoSidewallsComplete", "visibleBoundaryOwnershipVerified",
                                    "centralFloorTrackPresent", "manualTruthAppliedAtRuntime",
                                    "radialUContourOwnershipVerified",
                                    "wallRadialAlignmentDeg", "openingHalfWidthDeg",
                                    "radialEnvelopeExtraDeg", "radialEnvelopeDeg",
                                    "radialUContourChecks", "radialUContourChecksFailed",
                                )
                                if key in fixture_source_exclusion
                            }
                            if isinstance(fixture_source_exclusion, dict) else None
                        ),
                    )
                    if source_adjudication is not None:
                        output["sourceConsistencyAdjudication"] = source_adjudication
                    if (
                        "local_second_wall_diagnostic" in detector
                        and source_consistency["status"] == "rejected"
                        and not (
                            source_adjudication is not None
                            and source_adjudication["decision"] == "ACCEPTED_OVERRIDE"
                        )
                    ):
                        output["localSecondWallDiagnostic"] = diagnose_local_second_wall(
                            target_gray,
                            groove_center,
                            groove_outer_radius,
                            candidate,
                            refinement,
                            self.module.bilinear_sample,
                            self.module.parabolic_peak,
                            detector["groove_refinement"],
                            detector.get("sidewall_source_consistency"),
                            detector.get("local_second_wall_diagnostic"),
                            pixel_scale=scale,
                        )
                    source_effective_accepted = (
                        source_consistency["status"] == "accepted"
                        or (
                            source_adjudication is not None
                            and source_adjudication["decision"] == "ACCEPTED_OVERRIDE"
                            and source_adjudication["effectiveStatus"] == "accepted"
                            and source_adjudication["imagePoseReleaseAllowed"] is True
                        )
                    )
                    wall_recovery_used = wall_family_recovery_used(refinement)
                    recovery_requires_fixture_exclusion = bool(
                        candidate.get("provisionalRecognition") is True
                        or wall_recovery_used
                    )
                    recovery_without_fixture_exclusion = (
                        recovery_requires_fixture_exclusion
                        and not recovery_fixture_exclusion_verified(
                            output.get("fixtureSourceExclusion")
                        )
                    )
                    if recovery_without_fixture_exclusion:
                        return {
                            **output,
                            "physicalRefinementStatus": refinement["status"],
                            "status": "failed",
                            "failedChecks": list(dict.fromkeys(
                                list(refinement.get("failedChecks") or [])
                                + ["recovery_fixture_source_exclusion_not_verified"]
                            )),
                        }
                    if source_consistency["status"] == "rejected" and not source_effective_accepted:
                        return {
                            **output,
                            "physicalRefinementStatus": refinement["status"],
                            "status": "failed",
                            "failedChecks": list(dict.fromkeys(
                                list(refinement.get("failedChecks") or [])
                                + [
                                    f"source_consistency:{value}"
                                    for value in source_consistency["failedChecks"]
                                ]
                            )),
                        }
                    return output

                if is_refined and len(groove_candidates) == 1:
                    refinement = refine_candidate(groove_candidates[0])
                    diagnostics["grooveRefinement"] = refinement
                    diagnostics["grooveSourceConsistency"] = refinement.get("sourceConsistency")
                    if "sourceConsistencyCandidate" in refinement:
                        diagnostics["sidewallSourceConsistencyCandidate"] = refinement["sourceConsistencyCandidate"]
                    if "sourceConsistencyAdjudication" in refinement:
                        diagnostics["sidewallSourceConsistencyAdjudication"] = refinement[
                            "sourceConsistencyAdjudication"
                        ]
                    if "localSecondWallDiagnostic" in refinement:
                        diagnostics["localSecondWallDiagnostic"] = refinement["localSecondWallDiagnostic"]
                    groove_candidates = [{
                        **groove_candidates[0],
                        "refinedStartDeg": (
                            None if refinement["openingEndpointProfileDeg"] is None
                            else refinement["openingEndpointProfileDeg"][0]
                        ),
                        "refinedEndDeg": (
                            None if refinement["openingEndpointProfileDeg"] is None
                            else refinement["openingEndpointProfileDeg"][1]
                        ),
                        "grooveRefinement": refinement,
                    }]
                    diagnostics["grooveCandidates"] = groove_candidates
                    if refinement["status"] == "accepted":
                        pose_recognition_status = "accepted"
                elif is_refined and len(groove_candidates) > 1 and detector["ambiguity_resolution"]["enabled"]:
                    resolution = resolve_groove_candidates(
                        groove_candidates, refine_candidate, detector["ambiguity_resolution"],
                    )
                    diagnostics["grooveResolution"] = resolution
                    if resolution["status"] == "resolved":
                        selected = resolution["survivors"][0]
                        refinement = selected["grooveRefinement"]
                        diagnostics["grooveRefinement"] = refinement
                        diagnostics["grooveSourceConsistency"] = refinement.get("sourceConsistency")
                        if "sourceConsistencyCandidate" in refinement:
                            diagnostics["sidewallSourceConsistencyCandidate"] = refinement["sourceConsistencyCandidate"]
                        if "sourceConsistencyAdjudication" in refinement:
                            diagnostics["sidewallSourceConsistencyAdjudication"] = refinement[
                                "sourceConsistencyAdjudication"
                            ]
                        if "localSecondWallDiagnostic" in refinement:
                            diagnostics["localSecondWallDiagnostic"] = refinement["localSecondWallDiagnostic"]
                        groove_candidates = [{
                            **selected,
                            "refinedStartDeg": refinement["openingEndpointProfileDeg"][0],
                            "refinedEndDeg": refinement["openingEndpointProfileDeg"][1],
                        }]
                        diagnostics["grooveCandidates"] = groove_candidates
                        pose_recognition_status = "accepted"
                    else:
                        diagnostics["grooveRefinement"] = None
                        diagnostics["grooveSourceConsistency"] = None
                elif is_refined:
                    diagnostics["grooveRefinement"] = None
                    diagnostics["grooveSourceConsistency"] = None
                single_pose = build_single_groove_pose(
                    groove_candidates,
                    groove_center,
                    groove_outer_radius,
                    pose_config,
                    recognition_status=pose_recognition_status,
                    plc_mapping_confirmed=bool(
                        self.config["pose"].get("production_plc_mapping_confirmed", False)
                    ),
                )
                diagnostics["singleGroovePose"] = single_pose
                effective_failures = apply_polar_quality_adjudication(
                    diagnostics,
                    failures,
                    detector.get("polar_quality_adjudication"),
                )
                shadow_source_config = detector.get(
                    "groove_shadow_source_discrimination", {"enabled": False}
                )
                if shadow_source_config["enabled"]:
                    source_evidence = build_candidate_source_evidence(
                        recognition,
                        single_refinement=diagnostics.get("grooveRefinement"),
                        resolution=diagnostics.get("grooveResolution"),
                    )
                    resolution_status = (diagnostics.get("grooveResolution") or {}).get("status")
                    if single_pose["status"] == "accepted":
                        source_terminal_stage = (
                            "polar_quality" if "polar_score" in effective_failures else "valid"
                        )
                    elif resolution_status == "multiple_survived":
                        source_terminal_stage = "groove_ambiguity"
                    elif resolution_status == "none_survived":
                        source_terminal_stage = (
                            "source_consistency"
                            if any(
                                item["sourceConsistency"]["status"] == "failed"
                                for item in source_evidence
                            )
                            else "groove_refinement"
                        )
                    elif isinstance(diagnostics.get("grooveRefinement"), dict):
                        source_terminal_stage = (
                            "source_consistency"
                            if any(
                                item["sourceConsistency"]["status"] == "failed"
                                for item in source_evidence
                            )
                            else "groove_refinement"
                        )
                    else:
                        source_terminal_stage = (
                            "groove_ambiguity"
                            if recognition.get("acceptedCount", 0) > 1
                            else "groove_recognition"
                        )
                    diagnostics["grooveShadowSourceDiscrimination"] = (
                        classify_groove_shadow_sources(
                            source_evidence,
                            enabled=True,
                            upstream_accepted=True,
                            polar_quality_accepted="polar_score" not in effective_failures,
                            existing_pose_chain_allowed=(
                                single_pose["status"] == "accepted" and not effective_failures
                            ),
                            terminal_stage=source_terminal_stage,
                            locked_gate_versions={
                                "recognition": detector["groove_recognition"]["threshold_version"],
                                "refinement": detector["groove_refinement"]["threshold_version"],
                                "sourceConsistency": detector["sidewall_source_consistency"]["threshold_version"],
                                "ambiguity": detector["ambiguity_resolution"]["schema_version"],
                            },
                            strategy_version=shadow_source_config["strategy_version"],
                            raw_candidate_screening=fixture_candidate_screening,
                        )
                    )
                if single_pose["status"] != "accepted":
                    resolution_status = (diagnostics.get("grooveResolution") or {}).get("status")
                    if resolution_status == "none_survived":
                        attempts = (diagnostics.get("grooveResolution") or {}).get("attempts") or []
                        source_rejected = any(
                            any(str(value).startswith("source_consistency:") for value in
                                ((attempt.get("refinement") or {}).get("failedChecks") or []))
                            for attempt in attempts
                        )
                        if source_rejected:
                            code, stage = "GROOVE_SOURCE_INCONSISTENT", "groove_source_consistency"
                            message = "no ambiguous coarse candidate passed sidewall source consistency"
                        else:
                            code, stage = "GROOVE_REFINEMENT_FAILED", "groove_refinement"
                            message = "no ambiguous coarse groove candidate passed physical sidewall refinement"
                    elif is_refined and isinstance(diagnostics.get("grooveRefinement"), dict) and diagnostics["grooveRefinement"]["status"] == "failed":
                        failed_checks = diagnostics["grooveRefinement"].get("failedChecks") or ["unknown"]
                        if any(str(value).startswith("source_consistency:") for value in failed_checks):
                            code, stage = "GROOVE_SOURCE_INCONSISTENT", "groove_source_consistency"
                            message = (
                                "single real groove sidewalls are not from one physical source; checks="
                                + ",".join(map(str, failed_checks))
                            )
                        else:
                            code, stage = "GROOVE_REFINEMENT_FAILED", "groove_refinement"
                            message = (
                                "single real groove subpixel refinement failed; checks="
                                + ",".join(map(str, failed_checks))
                            )
                    else:
                        code = (
                            "GROOVE_RECOGNITION_AMBIGUOUS"
                            if single_pose["status"] == "ambiguous"
                            else "GROOVE_RECOGNITION_FAILED"
                        )
                        stage = "groove_recognition"
                        message = (
                            "single_real_groove requires exactly one accepted groove; "
                            f"accepted={single_pose['acceptedGrooveCount']}"
                        )
                    raise LegacyAdapterError(
                        code,
                        stage,
                        message,
                        diagnostics,
                    )
                candidate_deg = float(single_pose["imageMeasurement"]["profileAzimuthXRightClockwiseDeg"])
                diagnostics["candidateAzimuthImageDeg"] = candidate_deg
            else:
                if recognition["status"] != "accepted":
                    code = (
                        "GROOVE_RECOGNITION_AMBIGUOUS"
                        if recognition["status"] == "ambiguous"
                        else "GROOVE_RECOGNITION_FAILED"
                    )
                    raise LegacyAdapterError(
                        code, "groove_recognition",
                        f"accepted grooves {recognition['acceptedCount']} are insufficient for "
                        f"{recognition['minimumRequiredCount']} configured roles",
                        diagnostics,
                    )
                role_assignment = assign_roles(
                    [_candidate_from_dict(item) for item in groove_candidates],
                    detector["role_assignment"],
                    expected_offset_deg=math.degrees(float(polar_rotation)),
                )
                diagnostics["roleAssignment"] = role_assignment
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
        final_failures = effective_failures if mode == "single_real_groove" else failures
        if final_failures:
            raise LegacyAdapterError(
                "QUALITY_REJECTED", "quality_gate",
                f"failed quality checks: {', '.join(final_failures)}", diagnostics,
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
        elif mode == "single_real_groove":
            single_pose = diagnostics["singleGroovePose"]
            selected_id = single_pose["role"]["candidateId"]
            selected = next(item for item in diagnostics["grooveCandidates"] if item["candidateId"] == selected_id)
            confidence_parts = [
                min(1.0, float(polar_score) / max(1.0, 2.0 * float(detector["min_polar_score"]))),
                float(selected["grooveScore"]),
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
        mode = self.config["detector"].get("diagnostic_mode")
        if mode in {"multi_notch_roles", "single_real_groove"}:
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
        if (
            mode == "single_real_groove"
            and self.config["detector"]["single_groove_pose"]["schema_version"]
            == "single-real-groove-pose-config/2"
        ):
            if not pose.get("production_plc_mapping_confirmed"):
                raise LegacyAdapterError(
                    "PLC_MAPPING_UNCONFIRMED", "pose_mapping",
                    "image-frame correction is diagnostic until PLC mapping is confirmed",
                )
            measured = (float(candidate_image_deg) - 90.0 + 180.0) % 360.0 - 180.0
            target = float(self.config["detector"]["single_groove_pose"]["target"]["nominal_deg"])
            angle = (target - measured + 180.0) % 360.0 - 180.0
        else:
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
