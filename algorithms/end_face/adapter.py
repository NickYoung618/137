"""Reusable adapter that keeps the desktop core immutable."""

from __future__ import annotations

import time
from pathlib import Path

from tools.dataset_common import inspect_image

from algorithms.end_face import CORE_SOURCE_SHA256, core
from algorithms.end_face.contract import failure_result, sha256_file, success_result
from algorithms.end_face.quality import evaluate_quality, load_quality_policy
from algorithms.end_face.quality import policy_sha256
from algorithms.end_face.short_line_candidate import ShortLineCandidateEvaluator, load_candidate_config


class EndFaceInspector:
    def __init__(
        self,
        annotation: Path,
        quality_policy: Path,
        pixel_size: float = 1.0,
        short_line_candidate_config: Path | None = None,
    ):
        self.annotation = annotation.resolve()
        self.quality_policy_path = quality_policy.resolve()
        if pixel_size <= 0:
            raise ValueError("pixel-size must be greater than zero")
        if not self.annotation.is_file():
            raise FileNotFoundError(f"annotation does not exist: {self.annotation}")
        if not self.quality_policy_path.is_file():
            raise FileNotFoundError(f"quality policy does not exist: {self.quality_policy_path}")
        core_path = Path(core.__file__).resolve()
        if sha256_file(core_path) != CORE_SOURCE_SHA256:
            raise ValueError("immutable desktop A-end-face core SHA-256 mismatch")
        self.pixel_size = float(pixel_size)
        self.quality_policy = load_quality_policy(self.quality_policy_path)
        self.quality_provenance = {
            "localization": {
                "policyId": self.quality_policy["policyId"],
                "policySha256": policy_sha256(self.quality_policy),
            }
        }
        self.reference_model = core.build_reference_model(self.annotation)
        self.short_line_candidate: ShortLineCandidateEvaluator | None = None
        if short_line_candidate_config is not None:
            candidate_path = short_line_candidate_config.resolve()
            candidate_config = load_candidate_config(candidate_path)
            self.short_line_candidate = ShortLineCandidateEvaluator(
                self.reference_model,
                candidate_config,
                candidate_path,
            )

    def inspect(self, image: Path, task_id: str | None = None) -> dict:
        image = image.resolve()
        resolved_task_id = task_id or f"end-face:{image.stem}"
        started = time.perf_counter()
        try:
            if not image.is_file():
                raise FileNotFoundError(f"input image does not exist: {image}")
            image_info = inspect_image(image)
            measurements, shift_method = core.detect_measurements(self.reference_model, image, self.pixel_size)
            quality = evaluate_quality(
                measurements,
                shift_method,
                (int(image_info["width"]), int(image_info["height"])),
                self.quality_policy,
                self.quality_policy_path,
            )
            short_line_candidates = (
                self.short_line_candidate.evaluate_image(image, measurements, quality["featureQuality"])
                if self.short_line_candidate is not None
                else {}
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return success_result(
                task_id=resolved_task_id,
                image=image,
                image_info=image_info,
                annotation=self.annotation,
                reference=self.reference_model.reference_path,
                pixel_size=self.pixel_size,
                shift_method=shift_method,
                measurements=measurements,
                quality=quality,
                short_line_candidates=short_line_candidates,
                candidate_provenance=(
                    self.short_line_candidate.provenance if self.short_line_candidate is not None else None
                ),
                elapsed_ms=elapsed_ms,
            )
        except Exception as exc:
            return failure_result(
                task_id=resolved_task_id,
                image=image,
                annotation=self.annotation,
                error=exc,
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                quality=self.quality_provenance,
                candidate_provenance=(
                    self.short_line_candidate.provenance if self.short_line_candidate is not None else None
                ),
            )
