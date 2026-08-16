# Feature Specification: A2 回放验收与根因加固

**Feature Branch**: `008-a2-replay-integrity-hardening`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "对 Mac A2 全量 700 张回放进行根因性诊断，并按照 Spec Kit 流程修复已证实问题；不得用本批 acceptance 数据直接调参后宣称泛化。"

## Clarifications

### Session 2026-08-15

- No critical ambiguity required a new user question: unknown bad-image business semantics remain an explicit BLOCKED dependency, while authoritative final-state accounting, explicit dataset labels, effective configuration provenance, and fail-closed ambiguity handling can be repaired independently.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Obtain authoritative replay acceptance results (Priority: P1)

As an algorithm and quality reviewer, I need one authoritative replay report whose detection, guidance, failure, and direction totals are derived from final result fields, so that intermediate geometry cannot be mistaken for an actionable result.

**Why this priority**: The current 700-image review reports 22 images in position even though only 2 final results are valid and in position. Incorrect acceptance accounting can hide fail-closed decisions and is a direct safety risk.

**Independent Test**: Feed a mixed replay containing valid guidance, early circle failure, groove failure, and a quality-rejected record that still carries intermediate geometry. The report must reproduce the final result truth exactly and preserve a separate pre-quality diagnostic count.

**Acceptance Scenarios**:

1. **Given** a quality-rejected image with an accepted intermediate groove pose, **When** the replay is summarized, **Then** it is counted only as final `DETECTION_FAILED/NOT_AVAILABLE` and never as in-position or actionable guidance.
2. **Given** an early circle-localization failure without a complete intermediate pose, **When** the replay is summarized, **Then** it inherits the final detection failure state instead of a separate lowercase or missing state.
3. **Given** a failed result, **When** direction totals are reported, **Then** its null direction is kept separate from the valid `NONE` deadband direction.

---

### User Story 2 - Preserve dataset business semantics explicitly (Priority: P1)

As a quality owner, I need every image's dataset class, exclusion reason, and pose-usability authority to be explicit rather than inferred from a folder name, so that a product-quality defect is not silently treated as an unusable pose image.

**Why this priority**: The current Manifest labels all 700 images as normal while a path convention is used later to recover 200 bad images. The meaning of “bad” is not documented, so the reported 59% false-positive rate is conditional rather than authoritative.

**Independent Test**: Build and validate a Manifest from normal and nested bad paths using an explicit external class map. Unknown pose usability must remain unknown and must not automatically become a false-positive label.

**Acceptance Scenarios**:

1. **Given** an explicit class mapping for nested input paths, **When** a Manifest is generated, **Then** every matched image receives the declared class without hard-coding a Chinese folder name.
2. **Given** a bad-class image without an authoritative pose-usability decision, **When** acceptance metrics are computed, **Then** it is reported as business-semantics-blocked rather than automatically counted as a pose false positive.
3. **Given** an explicit `poseUsable=false` decision, **When** the image produces valid guidance, **Then** the conditional false-positive metric counts it and cites the label source.
4. **Given** images assigned to development, validation, test, and locked acceptance purposes, **When** their Manifest is validated, **Then** the same physical sample and source-image lineage cannot cross purposes.
5. **Given** the already-inspected 700-image replay, **When** a new algorithm iteration is evaluated, **Then** it remains a locked acceptance-regression set and is not repeatedly used to choose thresholds; a small declared smoke subset may check plumbing but cannot be reported as independent accuracy validation.

---

### User Story 3 - Reproduce the effective configuration (Priority: P1)

As a validation engineer, I need the exact effective detector configuration to satisfy its versioned contract and be hashable, including defaults used at runtime, so that Mac and server replay results can be reproduced without guessing omitted values.

**Why this priority**: Both transferred configurations omit a section required by the current configuration Schema, while runtime silently supplies defaults and only exposes them indirectly in diagnostics.

**Independent Test**: Validate both a fully explicit configuration and a compatible configuration that omits defaultable sections. Materializing either must produce the same complete, schema-valid effective configuration and stable hash when their effective behavior is identical.

**Acceptance Scenarios**:

1. **Given** a backward-compatible configuration with omitted defaultable fields, **When** it is loaded, **Then** the system can emit a complete effective configuration with all applied thresholds.
2. **Given** two configurations that differ only by omitted versus explicitly written defaults, **When** effective hashes are computed, **Then** their effective hashes match while their source-file hashes remain distinct.
3. **Given** an invalid explicit value, **When** configuration validation runs, **Then** it fails before image processing with a precise field error.

---

### User Story 4 - Resolve only provably unique groove ambiguities (Priority: P2)

As an operator, I want a frame with multiple coarse groove-like dark regions to recover only when exactly one candidate survives the already-required physical sidewall refinement, so that shadows are not selected merely because they have a slightly higher retrospective score.

**Why this priority**: Forty-one replay images have two accepted coarse groove candidates. A score-only choice is unsafe, but an existing independent sidewall-and-circle-intersection stage can provide stronger geometric evidence without introducing a new learned model or tuning on acceptance labels.

**Independent Test**: Use controlled candidates where only one, none, or multiple candidates have valid sidewalls. Only the exactly-one-refined case may become a detected single groove; all other cases remain fail-closed.

**Acceptance Scenarios**:

1. **Given** two coarse candidates and exactly one valid refined opening, **When** bounded ambiguity resolution runs, **Then** the valid refined opening is selected and all rejected candidates retain their evidence.
2. **Given** two candidates that both refine successfully, **When** ambiguity resolution runs, **Then** the result remains `GROOVE_RECOGNITION_AMBIGUOUS` with no guidance.
3. **Given** no candidate that refines successfully, **When** ambiguity resolution runs, **Then** the result is a clear refinement failure with no fallback to a coarse angle.
4. **Given** more candidates than the configured hard limit, **When** resolution is requested, **Then** processing fails closed without unbounded work.

---

### User Story 5 - Report root causes without acceptance-data tuning (Priority: P3)

As an algorithm owner, I need stage funnels, threshold margins, static-repeatability eligibility, and required-annotation queues so that the next improvement is chosen from evidence without changing production gates on the same acceptance set.

**Why this priority**: Normal failures are concentrated at specific circle and groove stages, but no per-image truth exists to justify gate changes. A structured evidence report prevents accidental overfitting.

**Independent Test**: Run the diagnostic summarizer over a fixed replay fixture and verify exact stage counts, boundary margins, label-availability status, and a prioritized annotation queue without changing runtime configuration.

**Acceptance Scenarios**:

1. **Given** explicit and non-explicit capture groups, **When** repeatability is reported, **Then** only explicit same-sample/same-condition groups receive an acceptance metric; inferred groups remain diagnostic-only.
2. **Given** records near a quality threshold, **When** root-cause diagnostics run, **Then** the observed margins are reported without recommending an automatically applied replacement threshold.
3. **Given** missing circle or groove truth, **When** repair impact is estimated, **Then** the report marks the affected outcome as blocked and identifies the minimum annotation needed.

### Edge Cases

- A final result is invalid but intermediate circle, groove, angle, or deadband fields are available.
- A failed result has null direction while a valid in-position result has direction `NONE`.
- Manifest paths use arbitrary locale-specific folder names or overlapping prefix rules.
- A class-map rule matches no files, one file matches multiple incompatible rules, or a declared path escapes the dataset root.
- A bad image is product-quality NG but remains geometrically usable for pose guidance.
- A source configuration omits defaults, explicitly repeats defaults, contains non-finite values, or contains unknown fields.
- Multiple coarse groove candidates survive; exactly one, none, or several pass physical refinement.
- The number of ambiguity candidates exceeds the configured work limit.
- Capture filenames appear in blocks of 20 but the final block contains multiple angle modes.
- Review artifacts are generated after a partial export failure and provenance for the retry is absent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Replay acceptance summaries MUST use final `result.valid`, `detectionStatus`, `guidanceStatus`, `rotationDirection`, and `error` as the authoritative outcome fields.
- **FR-002**: Intermediate circle, groove, refinement, and guidance states MUST be reported separately and MUST NOT increase final detected, in-position, or actionable-guidance counts.
- **FR-003**: Failed records MUST keep angle, correction, and direction unavailable; null direction MUST NOT be counted as valid `NONE`.
- **FR-004**: The summary MUST publish cross-field consistency checks and fail validation when mutually inconsistent final states are found.
- **FR-005**: Manifest generation MUST support an explicit, external, path-safe mapping from dataset paths to dataset class without hard-coding a site-specific folder name.
- **FR-006**: Dataset class, product-quality disposition, image-quality disposition, and pose usability MUST be modeled as separate concepts.
- **FR-007**: A pose false-positive rate MUST only be authoritative when `poseUsable` or an equivalent explicit guidance-eligibility label is available; folder class alone MUST produce a conditional metric with a blocker.
- **FR-008**: Manifest validation MUST reject conflicting class rules, unsafe paths, unsupported class values, and incomplete authoritative labels.
- **FR-009**: Source configuration identity and effective configuration identity MUST be distinct and independently hashable.
- **FR-010**: Every accepted configuration MUST be materializable as a complete effective configuration that passes the versioned configuration contract.
- **FR-011**: Omitted backward-compatible defaults and the same explicitly written defaults MUST produce the same effective identity.
- **FR-012**: Invalid explicit detector settings MUST fail before image processing with an actionable field-level diagnostic.
- **FR-013**: In single-real-groove mode, role/pose calculation MUST consume only a uniquely resolved physical groove candidate.
- **FR-014**: When multiple coarse groove candidates exist, optional ambiguity recovery MUST refine a bounded number of candidates using existing sidewall and outer-circle geometry; it MUST NOT choose by acceptance-set angle, directory class, fixed image angle, candidate number, or score alone.
- **FR-015**: Ambiguity recovery MUST succeed only when exactly one candidate passes all existing physical refinement gates; zero, multiple, or over-limit survivors MUST remain fail-closed.
- **FR-016**: Rejected candidates and their recognition/refinement evidence MUST remain in diagnostics after ambiguity recovery.
- **FR-017**: Existing legacy, paired, multi-role, and single-candidate paths MUST remain compatible and retain their existing fail-closed behavior.
- **FR-018**: Root-cause reporting MUST separate circle proposal, sparse circle, final physical circle, raw dark-region, groove recognition, groove refinement, and top-level quality stages.
- **FR-019**: Root-cause reporting MUST include sample counts and threshold margins while explicitly labeling retrospective separability analysis as non-authoritative.
- **FR-020**: Static repeatability acceptance MUST require explicit physical-sample and same-condition grouping and MUST use circular residuals; filename count or raw angle means MUST NOT manufacture groups.
- **FR-021**: The feature MUST provide an annotation queue identifying the minimum circle, groove-role, sidewall, bad-reason, and pose-usability evidence needed for each blocked repair class.
- **FR-022**: Original images, transferred replay artifacts, site paths, and manual truth MUST remain outside Git and MUST NOT become runtime inputs.
- **FR-023**: PLC and upstream integration remain out of scope; image-frame guidance and PLC execution authority MUST remain separate.
- **FR-024**: Production thresholds MUST NOT be changed solely to optimize this 700-image acceptance replay; any threshold change requires independent labeled development data and a held-out validation set.
- **FR-025**: Every evaluation Manifest MUST declare each image purpose as `development`, `validation`, `test`, or locked `acceptance`; the same physical sample and source-image lineage MUST NOT cross purposes.
- **FR-026**: Development, validation, test, and locked acceptance results MUST be reported separately; metrics from one purpose MUST NOT be relabeled as another.
- **FR-027**: The inspected 700-image replay MUST remain locked as acceptance regression evidence and MUST NOT be run repeatedly during implementation or used for threshold/model selection; full replay execution requires a recorded release-candidate reason and configuration identity.
- **FR-028**: Because only one human-annotated sample currently exists, it MAY serve as a geometric reference/development case but MUST NOT simultaneously serve as independent validation or test truth. Missing independent labeled validation/test data MUST remain explicit BLOCKED work.

### Key Entities

- **Final Replay Outcome**: Authoritative per-image detection, guidance, direction, validity, error, and fail-closed fields.
- **Intermediate Diagnostic Outcome**: Non-actionable circle, groove, refinement, quality, and pre-gate geometry states.
- **Dataset Semantics Record**: Dataset class, bad reason, product disposition, image disposition, pose usability, authority, and provenance for one image or an explicitly homogeneous group.
- **Source Configuration**: The exact user-provided configuration bytes and source hash.
- **Effective Configuration**: The complete validated settings after defaults, with a canonical identity independent of formatting or omission of defaults.
- **Groove Resolution Attempt**: The bounded set of coarse candidates, each candidate's physical refinement result, survivor count, and final uniqueness decision.
- **Root-Cause Report**: Stage funnel, consistency findings, threshold-margin distributions, label coverage, repeatability eligibility, and annotation queue.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the locked 700-record replay, the authoritative summary reports exactly 491 valid detections, 489 needing adjustment, 2 in position, and 209 unavailable, with no quality-rejected record counted as actionable.
- **SC-002**: On the same replay, direction reporting contains exactly 271 clockwise, 218 counterclockwise, 2 valid none, and 209 unavailable directions.
- **SC-003**: All 700 final results pass the result contract and all cross-field consistency checks; deliberately inconsistent fixtures fail with precise diagnostics.
- **SC-004**: Explicit dataset semantics reproduce 500 normal and 200 bad paths without any bad path being silently labeled normal; unknown pose usability is reported as blocked, not as an authoritative false positive.
- **SC-005**: Compatible omitted-default and explicit-default configurations materialize to byte-stable canonical content with identical effective hashes and pass the configuration contract.
- **SC-006**: Controlled ambiguity tests recover guidance when and only when exactly one candidate passes physical refinement; zero, two, and over-limit cases return no angle or correction.
- **SC-007**: All pre-existing legacy, paired, multi-role, and single-real-groove focused tests pass without output-contract regression.
- **SC-008**: Root-cause output reproduces the normal failure split 27/20/60/20 and bad-image final split 118/21/41/20 from final records while clearly marking bad-image pose semantics as blocked.
- **SC-009**: Repeatability remains `NOT_EVALUATED` for the transferred Manifest and becomes evaluable only in a fixture with explicit same-sample/same-condition grouping.
- **SC-010**: No repository diff contains source images, transferred replay files, absolute Mac/server data paths, manual truth as runtime input, or files larger than the established source-control limit.
- **SC-011**: Full unit and contract tests pass, and the diagnostic replay audit completes without invoking image detection, retraining, PLC writes, or upstream integration.
- **SC-012**: Split-leakage tests reject a physical sample or source lineage shared across development/validation/test/acceptance, and the report marks the current independent labeled validation/test sets as `NOT_AVAILABLE` rather than manufacturing them from filenames or the one annotated sample.

## Assumptions

- The transferred 700-result replay is a locked acceptance diagnostic input, not a development set for automatic threshold optimization.
- Final v3 result fields are authoritative for actionability; intermediate diagnostics remain valuable for root-cause analysis only.
- The label “bad” is not equivalent to pose unusable until quality or mechanical owners provide explicit semantics.
- Existing gyj outer-edge and robust circle fit, groove recognition, and subpixel sidewall refinement remain the reusable geometric foundation.
- Ambiguity recovery may reuse existing physical refinement, but it may not introduce a learned model or use the 85° target to decide which candidate is real.
- Current image coordinate and closed-loop guidance conventions from Spec 007 remain unchanged.
- PLC mapping remains blocked and outside this feature.

## Dependencies and Blocked Decisions

- **BLOCKED-B01**: Quality/production owners must define bad-reason categories and whether each category permits pose guidance before an authoritative bad-image false-positive gate can be implemented.
- **BLOCKED-B02**: Circle truth is required for the normal sparse/final circle failures before changing circle residual handling or thresholds.
- **BLOCKED-B03**: Real-groove and shadow labels are required for raw-zero, zero-accepted, and multiple-accepted replay groups before changing candidate-generation or recognition thresholds.
- **BLOCKED-B04**: Explicit physical-sample/capture-condition grouping and per-group truth are required before reporting production static repeatability.
- **BLOCKED-B05**: New physically isolated samples with reviewed circle/groove annotations are required to establish independent validation and test sets; the single current annotation and already-inspected 700-image replay cannot provide unbiased validation/test accuracy by themselves.

## Out of Scope

- Retrospectively selecting new production thresholds from the 700-image acceptance replay.
- Declaring all 200 bad-directory images unusable without explicit business labels.
- Training or introducing a learned detector.
- Changing the 85° target, angle convention, PLC mapping, upstream UI, or equipment control.
- Modifying or committing external images, replay outputs, or human annotations.
