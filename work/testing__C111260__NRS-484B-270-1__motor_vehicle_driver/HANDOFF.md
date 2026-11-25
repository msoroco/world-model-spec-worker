# testing__C111260__NRS-484B-270-1__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.270(1) — The driver of a motor vehicle shall not intentionally interfere with the movement of a person lawfully riding a bicycle, an electric bicycle or an electric scooter.
Assigned branch(es): Bicycle rider.
Cell: C111260 (intersection, travel, cyclist); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111260__NRS-484B-270-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Controlled bicycle encounter checkpoint

The exact bicycle-rider branch now has two planned case IDs, `testing__C111260__NRS-484B-270-1__motor_vehicle_driver__maintain_clearance` and `testing__C111260__NRS-484B-270-1__motor_vehicle_driver__cross_rider_path`, in `case-plan.json`, joined by `bicycle_encounter_behavior`. The difference is an ego controller command; map, routes, rider classification, cameras, duration and bicycle rider are fixed. This compares observable behavior without asserting lawful riding, intent or interference from geometry. The exact law also names electric bicycle and electric scooter riders; those alternatives remain explicitly pending CPU construction and source definitions.

`bicycle_encounter.py` source-gates the Native map, routes, bicycle classification and rider rules packets; proves crossing geometry; spawns the motor vehicle and bicycle through an injected CARLA-like API with cleanup after a partial spawn; and measures original continuous frame, blueprint, visual-rider and controller-command histories. `encounter_control.py` supplies both behavior commands. `comparison_audit.py` independently rejects missing original sources, changed fixed conditions and asserted legal verdicts. The assigned witness requires a human-powered bicycle satisfying NRS 484A.025, a distinct motor vehicle, rider conduct facts and unresolved legal terms; the implementation preserves those distinctions.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111260__NRS-484B-270-1__motor_vehicle_driver/tests -v` passed six tests. Log: `cpu-tests.log` (SHA256: 118366bd7ecc0c739d882b356a747e56194b1fb29eac8847c7a09f8727fb4058). Tests cover positive construction/measurement and negative source hash, source packet, geometry, failed spawn, comparison fixed condition, and legal-verdict branches. The source packets themselves must still be constructed from a surveyed real Native cell; these tests use textual mocks and are not physical evidence.

Remaining CPU work: build source-bound Native survey packets and all three rider modality variants; finish exact runner/config/construction, measurement finalizer, canonical semantic proposals, delivery audit, case-specific positive/negative compatibility, saved-only processing, manifest and risk-based candidate checks. Physical rider render, actual motion and four-view capture remain later GPU checks. Current status stays partial.

## Native map acquisition checkpoint

`native_site_survey.py` now reads the loaded Native map name and OpenDRIVE, samples every proposed ego and rider route point through Native waypoints, checks source distance and a junction readback, and seals the raw map and route packet. `bicycle_encounter.verify_site` checks that packet against its sealed raw map and waypoint readbacks before construction. The survey is an acquisition for the existing two human-powered bicycle cases; it makes no claim about rider classification, lawful riding, intention, interference or physical visibility. Classification and rule packets remain independently required. The source writer should run under `.runtime-work/` during local Native acquisition; its small CPU tests write only temporary text.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111260__NRS-484B-270-1__motor_vehicle_driver/tests -v` passed 11 tests; `cpu-tests.log` SHA256: d403544ecaa9f75d83c804dc8d4948c647c4e05280d50b125a686d2bbf136958.

Remaining CPU work: build exact electric-bicycle and electric-scooter alternatives where cell and actor sources support them, source-bound rider classification/rules, complete runner/config/construction/finalizer, canonical proposals, delivery audit, exact offline/positive/negative compatibility, saved-only processing and manifest. Actual Native motion and rendered rider visibility require later physical execution.

Assignment-scoped checkpoint: `.venv-cpu/bin/python worker_check.py --assignment testing__C111260__NRS-484B-270-1__motor_vehicle_driver --complete` passed (`cpu-static-check.log`, SHA256 4cab5a19669cdfd392ef3ae160e2829dab1a655429ad5f87f67077145a4bd365). The exact `--require-delivery-ready` check exited 1 because this package truthfully remains partial (`cpu-strict-check.log`, SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a). No external blocker or ready claim.

## Saved bicycle attempt checkpoint (2026-11-23)

`saved_attempt.py` validates an exact 900-frame, 20 Hz Original history for the two existing bicycle cases. It requires stable motor-vehicle/bicycle blueprint and actor IDs, contiguous telemetry frames, a per-frame camera join, an explicit command source and target-speed history, observed rider movement, and four distinct hash-bound camera videos. `probe_video` uses FFprobe decoded frame counts; the finalizer rejects missing streams, changed source bytes, duration or join gaps. It reports measured pose travel, center gap and command counts without treating a rider-visual annotation as a pixel proof. Pixel visibility and lawful-riding/intent/interference verdicts remain unverified.

Pinned preflight: `.venv-cpu/bin/python runtime.py preflight` exit 0, `cpu-preflight-nov23.log` SHA256 b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63. Focused suite: `.venv-cpu/bin/python -m unittest discover -s work/testing__C111260__NRS-484B-270-1__motor_vehicle_driver/tests -v` exit 0, 13 tests, `cpu-tests-nov23.log` SHA256 39f3963457b3241239d6001b5d530e0f6be659337dd2c5dc7eb81bdb88bc7035. Tests include a real 3-frame FFmpeg/FFprobe stream; the long saved history uses textual mocks and is not physical evidence.

Next CPU work: connect this finalizer to exact construction/capture bundles and the pinned saved-processing format; source-seal Native rider classification/rules; implement electric-bicycle and electric-scooter alternatives, semantic proposals, exact offline and positive/negative compatibility, independent saved delivery audit and manifest. Keep current result partial until the exact strict assignment gate passes.
Scoped static gate exit 0: `cpu-static-nov23.log` SHA256 4cab5a19669cdfd392ef3ae160e2829dab1a655429ad5f87f67077145a4bd365.
Scoped strict gate exit 1: `cpu-strict-nov23.log` SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

## 2026-11-23 saved full camera decode checkpoint

`delivery_decode.py` independently reads the four sealed saved camera files, checks distinct source paths and 20 Hz stream frame counts, fully decodes every frame through FFmpeg `framemd5`, hashes each full decode receipt and rechecks source bytes after decoding. `finalize_delivery` joins those receipts to the saved event measurement and rejects metadata disagreement. The small FFmpeg fixture tests all four streams, exact frame count, changed source bytes, and a newly rehashed invalid video. This is software source/decode evidence only: rider pixel visibility, actual encounter, lawful riding, intent and interference remain unverified.

The 14-test focused suite, pinned preflight and scoped static check pass. Exact scoped strict exits 1 on truthful partial status; current commands and SHA-256 log receipts are in `result.json`. Canonical case bundles, remaining modality alternatives, semantic proposals, source-bound offline/compatibility and a complete independent delivery audit remain worker-owned CPU tasks.

## 2026-11-24 original video stream count proof

`saved_attempt.probe_video` now inventories every video stream in each original camera file and requires exactly one. Previously selecting `v:0` could accept a second video stream while saved finalization and full decode ignored it. A real two-stream FFV1 fixture proves rejection. The 15-test assignment suite passes, with test scratch under `.runtime-work/`; pinned preflight and scoped static pass. Exact scoped strict exits 1 on truthful partial. Four SHA-bound logs are in `result.json`. This is source/decode integrity, not rider pixel visibility.

Remaining CPU work: source-bound Native rider classification/rules, exact electric-bicycle and scooter alternatives, canonical bundles and semantic proposals, positive/negative compatibility, saved-only processing and independent delivery audit. Original encounter motion, visibility, lawful riding, intent and interference remain unverified.

## 2026-11-24 reviewed rider source checkpoint

`rider_sources.py` verifies a sealed inventory for human-powered bicycle, electric bicycle and electric scooter observations. Each device/rider/rule review binds a separate original asset and is joined to the exact assignment, blueprint and jurisdiction. The Native constructor and saved finalizer require that inventory; comparison audit fixes rider kind and its inventory hash. No review packet supplies a legal verdict. The 17-test focused suite includes electric modality construction, original-asset tamper, changed review observations and verdict injection negatives. This is CPU source-schema proof and an injected Native API fixture, not proof that a real selected Native actor or rider conduct has been reviewed.

`cpu-rider-source-tests.log` passed (17 tests); `cpu-rider-source-static.log` passed; `cpu-rider-source-strict.log` exited 1 because status remains partial. The strict gate has not passed. Next CPU work: bind an actual original Native rider/site review to the two exact cases, then author exact canonical construction bundles, selected semantic proposals and manifest, pinned offline/positive-negative compatibility, saved-only processing, physical-preparation tests and full independent delivery audit. Physical realization and pixel visibility remain later local GPU checks.

## 2026-11-25 independent delivery audit checkpoint

`delivery_audit.py` now validates the two exact case IDs against a sealed original source index, verified rider/site packets, 20 Hz frame map and actor events, four original PNG sequences, complete video decodes, independent per-view pixel samples and sampled PNG-to-video RGB content. A separate physical review must name the original first/last frame and confirm the observed encounter; it cannot supply a statutory verdict. The audit rejects missing or stale source identity, wrong case, video/decode mismatch, unresolved pixel samples, image/video difference and incomplete physical review. The local fixture uses actual FFmpeg video and PNG files under `.runtime-work/`; it does not establish a physical CARLA encounter.

The latest `cpu-rider-delivery-tests.log` passed 18 focused tests. `cpu-rider-delivery-static.log` passed. `cpu-rider-delivery-strict.log` exited 1 on truthful partial status. CPU work still required: exact canonical runner/config/construction and manifest, semantic proposals, offline and positive/negative compatibility receipts, saved-only processing and physical preparation. A real independently reviewed Native map, rider asset and conduct packet must be supplied during local execution; do not fabricate them from fixtures.
