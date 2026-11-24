# testing__C104084__NRS-484B-213-2a__motor_vehicle_driver

Status: partial CPU construction. Four exact crest cases are planned; no recording has been proposed as physically accepted.

Exact law: NRS 484B.213(2)(a); with 484B.213(3) — A vehicle must not be driven to the left side of the highway at any time: When approaching the crest of a grade or upon a curve in the highway where the driver’s view is obstructed within such distance as to create a hazard in the event another vehicle might approach from the opposite direction. Subsection 2 does not apply upon a one-way highway.
Assigned branch(es): Approaching a crest; obstructed-view condition; one-way exception absent by setup..
Cell: C104084 (hill_crest, travel, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C104084__NRS-484B-213-2a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

The exact law has separate crest and curve alternatives. This assignment's frozen
`hill_crest` layout supports the crest alternative; the curve alternative needs a
compatible cell binding in the batch-level branch allocation. Subsection 3's
one-way exception is represented as an explicit original lane-allocation case,
not inferred from the absence of an oncoming actor. No numeric hazard-distance
threshold exists in the supplied law, so the judgment remains unlabelled.

`case-plan.json` now lists four exact crest cases: `right_crest_obstructed`,
`left_crest_obstructed`, `left_crest_clear`, and `left_one_way_obstructed`, each
prefixed by this assignment ID. The three comparisons separately vary actual
left-side body motion, sampled crest-ray obstruction, and original one-way lane
allocation. The frozen evidence inventory has zero accepted recordings, so all
four remain planned captures rather than reuse claims. Each case now records its
physical risk: no source-bounded Native map crest or lane-direction packet has
yet been selected. No fallback is claimed without a tested alternate construction.

`crest_geometry.py` requires original waypoint source references, a same-road
opposing lane with opposite direction, aligned stations, and an actual sampled
grade intersecting the declared 1.4 m virtual-observer proxy ray. Its CPU tests
exercise both approach directions, reject a flat grade, and reject wrong lane
orientation or missing provenance. `comparison_audit.py` requires source-bound
packets and rejects missing sources, confounded fixed conditions and missing
planned differences. Its tests cover all three comparisons. These checks are
preparation code and synthetic unit evidence; they are not physical completion,
actual Native raycasts, delivered pixels, or a legal hazard conclusion.

Proof: `.venv-cpu/bin/python -m unittest discover -s work/testing__C104084__NRS-484B-213-2a__motor_vehicle_driver/tests -v` passed six tests in `cpu-tests.log` (hash in `result.json`). `.venv-cpu/bin/python worker_check.py --assignment testing__C104084__NRS-484B-213-2a__motor_vehicle_driver --complete` passed static checks in `assignment-check.log`. The exact strict command with `--require-delivery-ready` failed because this assignment is still partial; see `strict-gate.log`. CPU preflight passed with the pinned environment.

Next worker-owned work: bind a real Native hill-crest map and highway context to
these geometry checks; implement the four exact capture constructions, controller,
measurement/finalization code, source-bound diagnostics and positive/negative
compatibility proofs; author semantic proposals, saved-only processing and
independent delivery audits; then rerun the exact strict gate. The batch lead
owns any shared curve cell binding. Actual CARLA motion, visibility and video
quality remain later physical checks after CPU preparation.

### Native map binding follow-up

`native_map.py` now follows the original CARLA map's connected ego waypoints,
retrieves each adjacent lane waypoint, checks opposing headings, rejects route
termination/branching and road/lane changes, retains original map/road/lane
source references and elevation samples, and requires the sampled grade to
intersect the declared proxy ray. It imports no CARLA module at import time.
The added CPU fake-world tests cover a grade with an opposing lane and reject
flat grade, a same-direction adjacent lane, and a truncated route. All nine
assignment tests pass in the refreshed `cpu-tests.log`. These checks are a
source-gated map-selection implementation; a real CARLA map and actual vehicle
rays have not been exercised on this CPU host. The one-way case still needs a
separate original topology binder and is not certified by this two-way binder.

### One-way exception construction follow-up

`native_map.bind_one_way_crest` now follows an original Native ego lane and a distinct adjacent same-direction lane across the grade. It rejects absent, opposite-heading, changing-lane and flat topology and returns sampled crest-proxy blockers while retaining explicit original public-highway and one-way-authority source requirements. Map topology is only a construction selector, not proof of the subsection 3 legal designation. `comparison_audit.py` rejects a one-way exception packet without an original authority source reference and SHA256. Twelve CPU tests pass in `cpu-tests.log`; the SHA256 is in `result.json`.

Next CPU work: bind an actual original Native map and original highway/one-way authority source; implement exact case capture/controllers, finalizers, diagnostic recipes and positive/negative compatibility, saved-only delivery audits and semantic proposals. The curve alternative still needs the batch lead to bind a compatible curve cell. Actual CARLA raycasts, motion and pixels remain later physical checks.

The refreshed assignment static check (`.venv-cpu/bin/python worker_check.py --assignment testing__C104084__NRS-484B-213-2a__motor_vehicle_driver --complete`) exited 0 in `assignment-check.log`. The exact strict check with `--require-delivery-ready` exited 1 in `strict-gate.log` with `Preparation acceptance failed: partial/missing packages remain`; the package correctly retains `status: partial` until the remaining CPU deliverables and their proofs pass.

### Saved original crest observation follow-up (2026-11-24)

`saved_crest.py` joins byte-hashed original attempt sources for the four exact
crest case IDs: 20 Hz Native body history, original lane/highway context,
per-frame opposing-body corner rays, frame map, and four camera source files.
It rejects a changed or missing source, case/law drift, absent original
opposing-lane or one-way authority binding, frame gaps, ray/frame mismatches,
timestamp drift, and absent actor/body packets. It reports observed left-side
body and ray states, distance range and whether the intended construction
target was observed, while keeping hazard-distance judgment unresolved.
Text-only camera files in the CPU tests prove source binding only; media
decoding and physical pixel visibility are still unimplemented CPU/delivery
work and later physical checks. The one-way authority reference is required
but its external original document has not yet been independently validated.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s
work/testing__C104084__NRS-484B-213-2a__motor_vehicle_driver/tests -v`
passed 17 tests in `cpu-tests.log` (SHA256 in `result.json`). The saved join
is a source-observation component, not a canonical runtime finalizer or
acceptance receipt. Next CPU actions: implement exact Native controller/capture
with guaranteed cleanup and original camera acquisition, connect the saved
join to runtime finalization, build four positive/negative diagnostic recipes,
run offline/compatibility and saved-only delivery audits, and author proposals.
The exact scoped `worker_check.py --assignment testing__C104084__NRS-484B-213-2a__motor_vehicle_driver --complete` passed in `assignment-check.log`; the scoped `--require-delivery-ready` exited 1 in `strict-gate.log` because the package remains partial.

### Capture and media delivery construction follow-up (2026-11-24)

`native_capture.py` now acquires each exact crest case through a lazy Native adapter contract. It requires the original road/center/opposing-lane or one-way context at begin, 900 consecutive 20 Hz world frames by default, matched body/ray packets and four camera callback frame IDs per tick, then writes source-hashed original packet and video files. Its `finally` calls adapter cleanup on success and acquisition failures. Fake-adapter tests prove the capture-to-saved-observation join and cleanup on missing camera or lane packets. The adapter still needs a concrete CARLA implementation, map authority acquisition and world snapshot/restore.

`saved_crest.py` now requires 900 original frames by default and an explicit complete frame list for each of the four cameras; three-frame fixtures override the count only in tests. `delivery_media.py` reopens byte-hashed original camera MP4s, ffprobes full frame counts/rates/dimensions and decodes every frame with ffmpeg. It reports neither origin nor physical visibility as verified. Its tests create small videos, then reject changed/missing originals, wrong frame counts and corrupt bodies. All 24 focused CPU tests pass in `cpu-tests.log` (hash in `result.json`).

Remaining CPU work: implement the concrete Native adapter and source-bound original highway/one-way authority acquisition; bind the capture output to runtime finalization and exact offline/positive/negative compatibility checks; author semantic proposals and independent full delivery audit. The curve alternative needs a batch-level compatible cell. Actual CARLA motion, sight lines, and pixel visibility remain physical checks only after preparation.

### Source binding and media timing follow-up (2026-11-24)

`delivery_media.py` now verifies every original camera presentation timestamp against the planned 20 Hz sequence, in addition to source hash, nominal rate, frame count, dimensions and full decode. A CPU-generated MP4 with 20 frames and nominal 20 Hz but a delayed frame is rejected. `saved_crest.py` now requires the one-way authority hash in `lane-context.json` to equal bytes of the retained `one-way-authority.json` source inside the same attempt; `native_capture.py` requires this file before capture, includes it in the source-hash receipt and refuses an occupied attempt directory. Tests prove positive source joins, tampered authority rejection, cleanup and prior-original preservation. This establishes integrity of a supplied authority source, not whether that source legally designates the road one-way.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C104084__NRS-484B-213-2a__motor_vehicle_driver/tests -v` passes 27 tests; `cpu-tests.log` SHA256 is in `result.json`. Remaining CPU work is the concrete CARLA adapter, exact canonical finalizers, semantic proposals, per-case offline/positive-negative compatibility and saved-only delivery receipts, and full independent delivery audit. The batch lead owns the shared curve-cell allocation. Keep all physical and legal judgments unresolved pending original evidence.

The latest `.venv-cpu/bin/python worker_check.py --assignment testing__C104084__NRS-484B-213-2a__motor_vehicle_driver --complete` exits 0 (`assignment-check.log`). The exact scoped command with `--require-delivery-ready` exits 1 at `Preparation acceptance failed: partial/missing packages remain` (`strict-gate.log`). The result remains partial.

### Saved-only four-camera crest delivery join (2026-11-23)

`saved_delivery.py:process` opens the exact Native `source-hashes.json`, rejects extra or missing originals, joins `saved_crest.measure` with `delivery_media.audit`, and writes one receipt only after all 900 original frames and four complete camera streams pass the saved checks. It preserves the observation, source-manifest SHA256 and independent decoded-media hashes while leaving highway authority, physical visibility, hazard distance and legal judgment unresolved. A short three-frame CPU fixture exercises the same path with an explicit test-only duration; it does not stand for a full physical run.

The positive fixture and negative resealed-broken-media/unplanned-source cases pass with the existing suite: 29 CPU tests, `cpu-saved-delivery-tests.log` SHA256 `e4c9a1bfbece84c284d4fc276ef6832dbb9573283a9fdff7e2ee6e09119ac228`. Scoped static exits 0 (`cpu-saved-delivery-static.log`, SHA256 `f7103607cf441b4b4422aedc645f5c195966afff4737211c9e74cf1887c18534`). Exact scoped strict exits 1 on truthful partial status (`cpu-saved-delivery-strict.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`).

Next CPU work: implement concrete CARLA adapter and reviewed highway/one-way source authority, exact canonical case bundles and finalizers, positive/negative compatibility, semantic proposals and canonical processing integration. The curve branch still requires a compatible cell binding by the batch lead; actual camera visibility and physical crest behavior remain unverified.

### Saved Native finalizer and same-frame target proof (2026-11-24)

`analysis.py` now reads the sealed `source-hashes.json`, joins the exact case's
original body/ray/context/frame packets through `saved_crest.measure`, rejects
unplanned manifest entries, rechecks original source hashes, and emits
derived `trace.jsonl`, canonical `video_frames.jsonl`, and a
`native_output.validate_result`-checked `result.json`. It retains all original
source bytes, rejects prior derived outputs and changed original sources, and
leaves physical setup, behavior, maneuver, hazard distance and legal judgment
unconfirmed. It is an executable saved finalizer component; its empty recording
evidence and lack of a complete runtime package mean it is not yet a Core
compatibility receipt or accepted delivery.

`saved_crest.measure` now requires the relevant body position and four-corner
proxy-ray state on at least one *same* original frame. Separate left-side and
blocked-ray episodes no longer satisfy the construction target. The added CPU
test deliberately separates those episodes and verifies rejection. No claim is
made that a single coincident frame establishes the statutory hazard phrase.

Pinned `.venv-cpu/bin/python runtime.py preflight` exited 0 in
`cpu-finalizer-preflight.log`. The focused assignment suite passed 33 tests in
`cpu-finalizer-tests.log`; scoped static exited 0 in
`cpu-finalizer-static.log`; exact scoped strict exited 1 in
`cpu-finalizer-strict.log` because the package is still partial. Hashes and
reproduction commands are in `result.json`.

Next CPU actions: add exact case constructions, concrete lazy CARLA adapter and
world restoration, original road/one-way authority packets, declared recording
channels, four source-hashed diagnostic recipes with positive/negative runtime
compatibility, semantic proposals and independent delivery/comparison audits.
The lead owns any shared curve-cell binding. No GPU dependency is claimed for
these remaining preparation steps.

### Independent derived-result source join (2026-11-23)

`derived_audit.py` independently reopens sealed original crest packets and checks every saved `trace.jsonl` body/ray value, `video_frames.jsonl` Native/frame/camera identity, and `result.json` measured observation and target check. It rejects changed derived rows, changed frame identities, fabricated target measurements and unsupported physical-completion claims. Its receipt retains source-manifest and derived file hashes and explicitly leaves physical and legal acceptance unclaimed. This is a saved-only CPU integrity proof, not a full delivery audit or local canonical acceptance.

Pinned preflight, 36 focused tests and scoped static checks pass. The exact scoped strict gate exits 1 on truthful partial status. Reproduction commands, exit codes and SHA256-bound logs are in `result.json` under `cpu-derived-*.log`. Remaining CPU work: concrete CARLA adapter and authority acquisition, four exact canonical case bundles, semantic proposals, positive/negative compatibility and process-saved proofs, and full independent delivery audit. Curve alternative needs the batch lead to assign a compatible cell. Actual motion, rays and pixel visibility remain later physical checks.

### Independent saved delivery integrity join (2026-11-23)

`delivery_audit.py` independently reopens the sealed original crest packets and all four MP4s, rejoins the saved finalizer observation and decoded-media report with the derived trace, frame map and target checks, and requires the saved receipt to match a freshly computed source-bound value. It rejects a rewritten physical-visibility claim and a changed derived trace. Its receipt retains source, saved receipt, derived and video hashes and explicitly claims no physical or legal acceptance. This CPU fixture uses three generated frames per camera; a 900-frame original capture and local canonical delivery remain unverified.

Pinned preflight, 39 focused tests and scoped static pass. Exact scoped strict exits 1 on truthful partial status. Four new normalized log SHA256 receipts are in `result.json`. Concrete Native adapter, exact bundles, semantic proposals, compatibility, source authority review and canonical process-saved integration remain CPU work; the curve cell allocation remains lead-owned.

### Exact-law semantic proposal checkpoint (2026-11-23)

`build_semantic_proposals.py` binds the frozen NRS 484B.213(2)(a) text, assignment and case plan into five draft stage families and `proposals/semantic-index.json`. The four exact cases encode only requested side, crest-view setup and source road direction. Three comparisons are checked to vary one declared variable each: ego side, original view condition, or one-way exception. The proposal retains unresolved highway authority, crest/view and hazard-distance judgments and claims no physical or legal acceptance.

Forty-three focused CPU tests, pinned preflight and scoped static pass. Exact scoped strict exits 1 on truthful partial. Native adapter/site source review, canonical case bundles, offline and positive/negative compatibility, saved processing and delivery receipts remain.

- `cpu-semantic-build.log` SHA256 `b510007e8cc19be94be656b11be21499a834c686e97610528bdc9e90bafad098`; exit 0.
- `cpu-semantic-tests.log` SHA256 `82323a215b6d5a6b680becf55cbb6537ae4e5d611a3c369dd2122f974bcc349a`; exit 0.
- `cpu-semantic-preflight.log` SHA256 `53b2dc44115dca8de01b83baa4fc603d1e3637323751f2f477905f827df42191`; exit 0.
- `cpu-semantic-static.log` SHA256 `f7103607cf441b4b4422aedc645f5c195966afff4737211c9e74cf1887c18534`; exit 0.
- `cpu-semantic-strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`; exit 1.
