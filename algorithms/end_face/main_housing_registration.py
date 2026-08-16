"""Core-external main-housing instance selection and similarity registration.

The legacy detector remains authoritative for its own measurements. This
module deliberately accepts only reference and target images. It has no input
for 19/30 labels or endpoints, so neither legacy predictions nor a measurement
annotation can accidentally become a registration seed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from algorithms.end_face import core


REGISTRATION_VERSION = "main-housing-registration/2"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _finite(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("main-housing registration configuration must be finite")
    return number


def validate_registration_config(config: Mapping[str, Any]) -> None:
    required = {
        "downsampleFactor",
        "foregroundThreshold",
        "minimumComponentPixels",
        "minimumDiameterPx",
        "maximumAspectError",
        "minimumComponentFillRatio",
        "maximumComponentFillRatio",
        "radialRayCount",
        "minimumEdgeCoverageRatio",
        "maximumCircularResidualRatio",
        "minimumScale",
        "maximumScale",
        "minimumReferenceRadiusMarginRatio",
        "angularSamples",
        "radialSamples",
        "minimumRotationScore",
        "minimumRotationMargin",
        "rotationSeparationDeg",
        "minimumInstanceScore",
        "minimumInstanceMargin",
    }
    if not isinstance(config, Mapping):
        raise ValueError("registration config must be an object")
    missing = sorted(required - set(config))
    unknown = sorted(set(config) - required)
    if missing or unknown:
        raise ValueError(f"registration config keys invalid: missing={missing}, unknown={unknown}")
    for name in required:
        _finite(config[name])
    for name in ("downsampleFactor", "minimumComponentPixels", "radialRayCount", "angularSamples", "radialSamples"):
        value = config[name]
        if isinstance(value, bool) or int(value) != value or int(value) <= 0:
            raise ValueError(f"registration.{name} must be a positive integer")
    ordered_pairs = (
        ("minimumComponentFillRatio", "maximumComponentFillRatio"),
        ("minimumScale", "maximumScale"),
    )
    for lower, upper in ordered_pairs:
        if not 0.0 <= float(config[lower]) < float(config[upper]):
            raise ValueError(f"registration {lower}/{upper} must be ordered and non-negative")
    if float(config["minimumScale"]) <= 0.0:
        raise ValueError("registration.minimumScale must be positive")
    if not 0.0 <= float(config["minimumReferenceRadiusMarginRatio"]) < 1.0:
        raise ValueError("registration.minimumReferenceRadiusMarginRatio must be in [0, 1)")
    for name in (
        "maximumAspectError",
        "minimumEdgeCoverageRatio",
        "maximumCircularResidualRatio",
        "minimumRotationMargin",
        "minimumInstanceMargin",
    ):
        if float(config[name]) < 0.0:
            raise ValueError(f"registration.{name} must be non-negative")
    if float(config["minimumEdgeCoverageRatio"]) > 1.0:
        raise ValueError("registration.minimumEdgeCoverageRatio must not exceed 1")
    if float(config["maximumComponentFillRatio"]) > 1.0:
        raise ValueError("registration.maximumComponentFillRatio must not exceed 1")


@dataclass
class HousingHypothesis:
    component_index: int
    component_bounds_px: tuple[float, float, float, float]
    coarse_center: tuple[float, float]
    coarse_radius: float
    center: tuple[float, float]
    radius: float
    component_pixels: int
    component_fill_ratio: float
    aspect_ratio: float
    edge_point_count: int
    edge_coverage_ratio: float
    circular_residual_px: float
    circular_residual_ratio: float
    scale_to_reference: float | None = None
    rotation_deg: float | None = None
    rotation_score: float | None = None
    rotation_second_score: float | None = None
    rotation_margin: float | None = None
    instance_score: float | None = None
    gates: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe({
            "componentIndex": self.component_index,
            "componentBoundsPx": list(self.component_bounds_px),
            "coarseCenterPx": list(self.coarse_center),
            "coarseRadiusPx": self.coarse_radius,
            "centerPx": list(self.center),
            "radiusPx": self.radius,
            "componentPixels": self.component_pixels,
            "componentFillRatio": self.component_fill_ratio,
            "aspectRatio": self.aspect_ratio,
            "edgePointCount": self.edge_point_count,
            "edgeCoverageRatio": self.edge_coverage_ratio,
            "circularResidualPx": self.circular_residual_px,
            "circularResidualRatio": self.circular_residual_ratio,
            "scaleToReference": self.scale_to_reference,
            "rotationDeg": self.rotation_deg,
            "rotationScore": self.rotation_score,
            "rotationSecondScore": self.rotation_second_score,
            "rotationMargin": self.rotation_margin,
            "instanceScore": self.instance_score,
            "gates": self.gates,
        })


@dataclass
class RegistrationResult:
    valid: bool
    failure_reason: str | None
    reference_center: tuple[float, float]
    reference_radius: float
    hypotheses: list[HousingHypothesis]
    reference_selection: dict[str, Any] = field(default_factory=dict)
    selected_index: int | None = None
    runner_up_index: int | None = None
    selection_margin: float | None = None
    target_center: tuple[float, float] | None = None
    target_radius: float | None = None
    scale: float | None = None
    rotation_deg: float | None = None
    rotation_score: float | None = None
    rotation_second_score: float | None = None
    rotation_margin: float | None = None
    checks: list[dict[str, Any]] = field(default_factory=list)

    def project_points(
        self,
        points: Sequence[Sequence[float]],
    ) -> tuple[tuple[float, float], ...]:
        if not self.valid or self.target_center is None or self.scale is None or self.rotation_deg is None:
            raise ValueError("cannot project points through an invalid main-housing registration")
        transform = core.SimilarityTransform(
            self.reference_center,
            self.target_center,
            self.scale,
            math.radians(self.rotation_deg),
            REGISTRATION_VERSION,
        )
        return tuple(transform.apply_point((float(point[0]), float(point[1]))) for point in points)

    def inverse_points(
        self,
        points: Sequence[Sequence[float]],
    ) -> tuple[tuple[float, float], ...]:
        if not self.valid or self.target_center is None or self.scale is None or self.rotation_deg is None:
            raise ValueError("cannot invert points through an invalid main-housing registration")
        transform = core.SimilarityTransform(
            self.reference_center,
            self.target_center,
            self.scale,
            math.radians(self.rotation_deg),
            REGISTRATION_VERSION,
        )
        return tuple(transform.inverse_point((float(point[0]), float(point[1]))) for point in points)

    def to_dict(self) -> dict[str, Any]:
        transform = None
        if self.target_center is not None and self.scale is not None and self.rotation_deg is not None:
            transform = {
                "referenceCenterPx": list(self.reference_center),
                "targetCenterPx": list(self.target_center),
                "scale": self.scale,
                "rotationDeg": self.rotation_deg,
                "method": REGISTRATION_VERSION,
            }
        return _json_safe({
            "registrationVersion": REGISTRATION_VERSION,
            "valid": self.valid,
            "failureReason": self.failure_reason,
            "reference": {
                "centerPx": list(self.reference_center),
                "radiusPx": self.reference_radius,
                "selection": self.reference_selection,
            },
            "hypotheses": [hypothesis.to_dict() for hypothesis in self.hypotheses],
            "selectedIndex": self.selected_index,
            "runnerUpIndex": self.runner_up_index,
            "selectionMargin": self.selection_margin,
            "transform": transform,
            "rotationScore": self.rotation_score,
            "rotationSecondScore": self.rotation_second_score,
            "rotationMargin": self.rotation_margin,
            "checks": self.checks,
        })


def _gate(name: str, passed: bool, rule: Any, observed: Any) -> dict[str, Any]:
    return {"id": name, "required": True, "passed": bool(passed), "rule": rule, "observed": observed}


def _connected_components(mask: np.ndarray, minimum_pixels: int) -> list[tuple[np.ndarray, np.ndarray]]:
    height, width = mask.shape
    visited = np.zeros(mask.shape, dtype=bool)
    components: list[tuple[np.ndarray, np.ndarray]] = []
    for seed_y, seed_x in zip(*np.where(mask & ~visited), strict=True):
        if visited[seed_y, seed_x]:
            continue
        visited[seed_y, seed_x] = True
        queue: list[tuple[int, int]] = [(int(seed_y), int(seed_x))]
        xs: list[int] = []
        ys: list[int] = []
        for y, x in queue:
            xs.append(x)
            ys.append(y)
            for dy, dx in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
                ny = y + dy
                nx = x + dx
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not visited[ny, nx]:
                    visited[ny, nx] = True
                    queue.append((ny, nx))
        if len(xs) >= minimum_pixels:
            components.append((np.asarray(xs, dtype=np.int32), np.asarray(ys, dtype=np.int32)))
    components.sort(key=lambda item: len(item[0]), reverse=True)
    return components


def _rotation_signature(
    gray: np.ndarray,
    center: tuple[float, float],
    radius: float,
    angular_samples: int,
    radial_samples: int,
) -> np.ndarray:
    return core.annular_angular_signature(
        gray,
        center,
        radius * 0.58,
        radius * 0.98,
        angle_count=angular_samples,
        radial_count=radial_samples,
    )


def _estimate_rotation(
    reference_signature: np.ndarray,
    target_signature: np.ndarray,
    separation_deg: float,
) -> tuple[float, float, float, float]:
    count = len(reference_signature)
    correlation = np.fft.ifft(
        np.fft.fft(target_signature) * np.conj(np.fft.fft(reference_signature))
    ).real / float(count)
    peak_index = int(np.argmax(correlation))
    signed_index = peak_index if peak_index <= count // 2 else peak_index - count
    subpixel = core.parabolic_peak(correlation.tolist(), peak_index)
    rotation_deg = 360.0 * (signed_index + subpixel) / float(count)
    separation = max(1, int(round(separation_deg * count / 360.0)))
    indices = np.arange(count)
    circular_distance = np.minimum((indices - peak_index) % count, (peak_index - indices) % count)
    separated = correlation[circular_distance >= separation]
    second = float(np.max(separated)) if separated.size else -1.0
    score = float(correlation[peak_index])
    return rotation_deg, score, second, score - second


class MainHousingRegistrar:
    """Register an image-only reference to an independently selected target instance."""

    def __init__(
        self,
        reference_gray: np.ndarray,
        config: Mapping[str, Any],
    ):
        validate_registration_config(config)
        reference = np.asarray(reference_gray, dtype=np.float64)
        if reference.ndim != 2 or not reference.size:
            raise ValueError("main-housing reference must be a non-empty grayscale image")
        self.reference_gray = reference
        self.config = dict(config)
        supported = [
            hypothesis
            for hypothesis in self._enumerate(reference)
            if all(gate["passed"] for gate in hypothesis.gates)
        ]
        supported.sort(key=lambda item: item.radius, reverse=True)
        if not supported:
            raise ValueError("reference image has no supported main-housing instance")
        selected = supported[0]
        runner = supported[1] if len(supported) > 1 else None
        radius_margin_ratio = (
            (selected.radius - runner.radius) / selected.radius
            if runner is not None and selected.radius > 0
            else 1.0
        )
        minimum_margin = float(config["minimumReferenceRadiusMarginRatio"])
        if radius_margin_ratio < minimum_margin:
            raise ValueError(
                "reference instance ambiguous: dominant radius margin "
                f"{radius_margin_ratio:.6f} is below {minimum_margin:.6f}"
            )
        self.reference_hypothesis = selected
        self.reference_selection = {
            "hypothesisCount": len(supported),
            "selectedComponentIndex": selected.component_index,
            "runnerUpComponentIndex": runner.component_index if runner is not None else None,
            "runnerUpRadiusPx": runner.radius if runner is not None else None,
            "radiusMarginRatio": radius_margin_ratio,
            "minimumRadiusMarginRatio": minimum_margin,
            "source": "image_circle_dominance",
        }
        self.reference_signature = _rotation_signature(
            reference,
            self.reference_hypothesis.center,
            self.reference_hypothesis.radius,
            int(config["angularSamples"]),
            int(config["radialSamples"]),
        )

    def _enumerate(self, gray: np.ndarray) -> list[HousingHypothesis]:
        config = self.config
        factor = int(config["downsampleFactor"])
        small = gray[::factor, ::factor]
        mask = small >= float(config["foregroundThreshold"])
        components = _connected_components(mask, int(config["minimumComponentPixels"]))
        hypotheses: list[HousingHypothesis] = []
        for component_index, (xs, ys) in enumerate(components):
            min_x = int(xs.min())
            max_x = int(xs.max())
            min_y = int(ys.min())
            max_y = int(ys.max())
            width = float((max_x - min_x + 1) * factor)
            height = float((max_y - min_y + 1) * factor)
            diameter = (width + height) * 0.5
            aspect_error = abs(width - height) / max(width, height, 1.0)
            fill_ratio = len(xs) / float((max_x - min_x + 1) * (max_y - min_y + 1))
            if diameter < float(config["minimumDiameterPx"]):
                continue
            if aspect_error > float(config["maximumAspectError"]):
                continue
            if not float(config["minimumComponentFillRatio"]) <= fill_ratio <= float(config["maximumComponentFillRatio"]):
                continue
            coarse_center = (
                ((min_x + max_x + 1) * factor - 1.0) * 0.5,
                ((min_y + max_y + 1) * factor - 1.0) * 0.5,
            )
            coarse_radius = diameter * 0.5
            points: list[tuple[float, float]] = []
            for angle in np.linspace(0.0, 2.0 * math.pi, int(config["radialRayCount"]), endpoint=False):
                point = core.outer_boundary_edge_point(gray, coarse_center, float(angle), coarse_radius)
                if point is None:
                    continue
                radial_distance = math.hypot(point[0] - coarse_center[0], point[1] - coarse_center[1])
                if abs(radial_distance - coarse_radius) <= max(24.0, coarse_radius * 0.16):
                    points.append(point)
            fitted = core.robust_fit_circle(points, (coarse_center[0], coarse_center[1], coarse_radius))
            distances = np.asarray(
                [math.hypot(x - fitted[0], y - fitted[1]) for x, y in points],
                dtype=np.float64,
            )
            residual = float(np.median(np.abs(distances - fitted[2]))) if distances.size else math.inf
            coverage = len(points) / float(config["radialRayCount"])
            residual_ratio = residual / fitted[2] if math.isfinite(residual) and fitted[2] > 0 else math.inf
            gates = [
                _gate("edge_coverage", coverage >= float(config["minimumEdgeCoverageRatio"]), config["minimumEdgeCoverageRatio"], coverage),
                _gate("circular_residual", residual_ratio <= float(config["maximumCircularResidualRatio"]), config["maximumCircularResidualRatio"], residual_ratio),
            ]
            hypotheses.append(HousingHypothesis(
                component_index=component_index,
                component_bounds_px=(min_x * factor, min_y * factor, (max_x + 1) * factor, (max_y + 1) * factor),
                coarse_center=coarse_center,
                coarse_radius=coarse_radius,
                center=(float(fitted[0]), float(fitted[1])),
                radius=float(fitted[2]),
                component_pixels=int(len(xs)),
                component_fill_ratio=float(fill_ratio),
                aspect_ratio=float(width / max(height, 1.0)),
                edge_point_count=len(points),
                edge_coverage_ratio=coverage,
                circular_residual_px=residual,
                circular_residual_ratio=residual_ratio,
                gates=gates,
            ))
        # One physical housing often contributes several disconnected concentric
        # threshold rings. Keep the largest proposal per center cluster so those
        # rings cannot masquerade as competing instances.
        deduplicated: list[HousingHypothesis] = []
        for hypothesis in sorted(hypotheses, key=lambda item: item.radius, reverse=True):
            if any(
                math.hypot(hypothesis.center[0] - kept.center[0], hypothesis.center[1] - kept.center[1])
                <= 0.18 * min(hypothesis.radius, kept.radius)
                for kept in deduplicated
            ):
                continue
            deduplicated.append(hypothesis)
        return deduplicated

    def register(self, target_gray: np.ndarray) -> RegistrationResult:
        target = np.asarray(target_gray, dtype=np.float64)
        if target.ndim != 2 or not target.size:
            raise ValueError("main-housing target must be a non-empty grayscale image")
        hypotheses = self._enumerate(target)
        reference = self.reference_hypothesis
        config = self.config
        qualified: list[HousingHypothesis] = []
        for hypothesis in hypotheses:
            scale = hypothesis.radius / reference.radius
            hypothesis.scale_to_reference = scale
            scale_ok = float(config["minimumScale"]) <= scale <= float(config["maximumScale"])
            support_ok = all(gate["passed"] for gate in hypothesis.gates)
            hypothesis.gates.append(_gate(
                "scale",
                scale_ok,
                [config["minimumScale"], config["maximumScale"]],
                scale,
            ))
            if not support_ok or not scale_ok:
                continue
            target_signature = _rotation_signature(
                target,
                hypothesis.center,
                hypothesis.radius,
                int(config["angularSamples"]),
                int(config["radialSamples"]),
            )
            rotation, score, second, margin = _estimate_rotation(
                self.reference_signature,
                target_signature,
                float(config["rotationSeparationDeg"]),
            )
            hypothesis.rotation_deg = rotation
            hypothesis.rotation_score = score
            hypothesis.rotation_second_score = second
            hypothesis.rotation_margin = margin
            circle_score = max(0.0, min(1.0, hypothesis.edge_coverage_ratio)) * max(
                0.0,
                1.0 - hypothesis.circular_residual_ratio / max(float(config["maximumCircularResidualRatio"]), 1e-9),
            )
            log_scale_span = max(
                abs(math.log(float(config["minimumScale"]))),
                abs(math.log(float(config["maximumScale"]))),
                1e-9,
            )
            scale_score = max(0.0, 1.0 - abs(math.log(max(scale, 1e-9))) / log_scale_span)
            appearance_score = max(0.0, min(1.0, (score + 1.0) * 0.5))
            hypothesis.instance_score = 0.35 * circle_score + 0.20 * scale_score + 0.45 * appearance_score
            hypothesis.gates.extend([
                _gate("rotation_score", score >= float(config["minimumRotationScore"]), config["minimumRotationScore"], score),
                _gate("rotation_margin", margin >= float(config["minimumRotationMargin"]), config["minimumRotationMargin"], margin),
                _gate("instance_score", hypothesis.instance_score >= float(config["minimumInstanceScore"]), config["minimumInstanceScore"], hypothesis.instance_score),
            ])
            if all(gate["passed"] for gate in hypothesis.gates):
                qualified.append(hypothesis)

        qualified.sort(key=lambda item: float(item.instance_score), reverse=True)
        if not qualified:
            return RegistrationResult(
                valid=False,
                failure_reason="no_supported_instance",
                reference_center=reference.center,
                reference_radius=reference.radius,
                hypotheses=hypotheses,
                reference_selection=self.reference_selection,
                checks=[_gate("supported_instance", False, "at least one gated instance", 0)],
            )
        selected = qualified[0]
        runner = qualified[1] if len(qualified) > 1 else None
        margin = float(selected.instance_score) - float(runner.instance_score) if runner is not None else 1.0
        margin_ok = margin >= float(config["minimumInstanceMargin"])
        checks = [
            _gate("supported_instance", True, "at least one gated instance", len(qualified)),
            _gate("instance_margin", margin_ok, config["minimumInstanceMargin"], margin),
        ]
        if not margin_ok:
            return RegistrationResult(
                valid=False,
                failure_reason="instance_ambiguous",
                reference_center=reference.center,
                reference_radius=reference.radius,
                hypotheses=hypotheses,
                reference_selection=self.reference_selection,
                selected_index=selected.component_index,
                runner_up_index=runner.component_index if runner is not None else None,
                selection_margin=margin,
                checks=checks,
            )
        return RegistrationResult(
            valid=True,
            failure_reason=None,
            reference_center=reference.center,
            reference_radius=reference.radius,
            hypotheses=hypotheses,
            reference_selection=self.reference_selection,
            selected_index=selected.component_index,
            runner_up_index=runner.component_index if runner is not None else None,
            selection_margin=margin,
            target_center=selected.center,
            target_radius=selected.radius,
            scale=selected.scale_to_reference,
            rotation_deg=selected.rotation_deg,
            rotation_score=selected.rotation_score,
            rotation_second_score=selected.rotation_second_score,
            rotation_margin=selected.rotation_margin,
            checks=checks,
        )
