# testing__C111260__NRS-484B-270-5a__motor_vehicle_driver

Status: partial construction and saved-source checkpoint. Six exact cases are proposed; no physical recording or legal conclusion is claimed.

Exact law: NRS 484B.270(5)(a) — The driver of a motor vehicle shall: Exercise due care to avoid a collision with a person riding a bicycle, an electric bicycle or an electric scooter.
Assigned branch(es): Person riding a bicycle.
Cell: C111260 (intersection, travel, cyclist); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111260__NRS-484B-270-5a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and comparison checkpoint

Six exact cases now map bicycle, electric bicycle and electric scooter to observed brake/maintain pairs; three comparisons hold Native map, rider type, routes, camera plan, duration and starting speeds fixed. There are no frozen accepted recordings or exact-law judgment ranges. `case-plan.json` carries case IDs, evidence gap, observations and requirement dispositions. This is a construction target, not measured delivery or a due-care conclusion.

`cyclist_encounter.py` validates original map route crossing and mounted rider classification, spawns the motor vehicle and rider with source-selected blueprints and cleanup, computes an engineering response trigger, and audits continuous 20 Hz original Native actor/gap/contact/response samples. `comparison_audit.py` independently rejects missing source histories, changed fixed conditions and unobserved response. `tests/` exercises positive and negative paths.

CPU proof: `.venv-cpu/bin/python -m unittest discover -s work/testing__C111260__NRS-484B-270-5a__motor_vehicle_driver/tests -v` passed 12 tests; `cpu-tests.log` SHA256 316da4e1f72eace539616763d1255a5baf84c234d222725e7cd6f9e30118210c. Assignment strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C111260__NRS-484B-270-5a__motor_vehicle_driver --complete --require-delivery-ready` fails `Preparation acceptance failed: partial/missing packages remain`; log `strict-gate.log` SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

Remaining CPU work: wire the selected Native map packet into the canonical runner/config/construction and per-case bundles; implement source-hashed case-specific finalizer, full 900-frame capture and delivery audit; run exact offline, positive/negative compatibility and saved-only proofs for every case; write semantic stage proposals and execution manifest. Physical CARLA motion, rider visibility and video quality remain later verification.

## 2026-11-24 saved encounter finalizer checkpoint

`saved_encounter.py` now joins an exact-case original Native encounter packet to SHA256-bound site, 900-frame 20 Hz history and four camera frame maps. It confines all source paths to the attempt directory, revalidates the map's crossing route and statutory rider classification with `cyclist_encounter.py`, and checks the observed rider identity, mounted state, response, gap/contact and frame continuity. It rejects a changed case, missing/tampered source, nonoriginal request history, missing camera, frame mismatch and path escape. The returned observation explicitly leaves full video decode, actual pixels, physical completion and due-care judgment unresolved. The local tests use synthetic small text packets solely to exercise software checks. The packet is not yet bound to a canonical Native receipt; that is CPU work.

`.venv-cpu/bin/python -m unittest discover -s work/testing__C111260__NRS-484B-270-5a__motor_vehicle_driver/tests -v` passed 17 tests; `cpu-tests.log` SHA256 9e0c0dc97d200f893871f3b7e4387ea0559d98e055605bdb65a5543e4976b24e. `.venv-cpu/bin/python worker_check.py --assignment testing__C111260__NRS-484B-270-5a__motor_vehicle_driver --complete` passed; `static-gate.log` SHA256 f64ad44f5d127b586b1fb76505cab0d9d90073885ce063d9098ced2614020366. The exact command with `--require-delivery-ready` exited 1 because this result remains partial; `strict-gate.log` SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

Next CPU steps: bind this packet to a canonical sealed Native result, implement actual 900-frame sensor acquisition and source readback, wire the runner and all six exact case bundles, implement semantic proposals, compatibility and saved-only proofs, then independent delivery and comparison audits and manifest. Actual motion and camera visibility require later local physical review.

## 2026-11-24 original sensor capture and pixel audit checkpoint

`native_capture.py` now accepts synchronous original world ticks, source-backed actor samples and four named original PNG sensor callbacks for exactly 900 frames at 20 Hz. It validates map/rider construction, original actor identity/response, continuous world frame IDs, per-camera frame joins and camera callback presence before sealing attempt-local source JSON and four PNG archives with SHA256 references. `audit_original_pixels` independently reopens all 3,600 saved PNG entries, fully decodes each image, and rejects stale media hashes, changed frame identities, missing camera streams and corrupt images even if source hashes are updated. This is a CPU interface and does not claim physical visibility or a legal due-care judgment. The prospective 1080p capture profile and composed video are not yet implemented here.

Focused proof: `.venv-cpu/bin/python -m unittest discover -s work/testing__C111260__NRS-484B-270-5a__motor_vehicle_driver/tests -v` passed 22 tests; `cpu-tests.log` SHA256 ac0e5e65f09ca16edaa864548bbf7a74f1a7e9990636b863577c58690e1f0b32. Scoped static check exited 0; `static-gate.log` SHA256 f64ad44f5d127b586b1fb76505cab0d9d90073885ce063d9098ced2614020366. Exact scoped strict check exited 1 because this package remains partial; `strict-gate.log` SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

Next CPU construction: bind this interface to a canonical Native runner and per-case configurations; retain lossless composed video at the required profile; add exact offline and positive/negative compatibility receipts, semantic proposals, execution manifest, saved-only path and independent delivery acceptance audit.

## 2026-11-23 independent saved-source audit checkpoint

`delivery_audit.py` now independently joins the externally SHA256-bound original acquisition packet, exact-case actor history and all 3,600 original camera PNGs. It rejects packet hash drift, case mismatch, unsupported adapter attestation, missing source history and corrupt/stale pixel sources. Its returned observations keep composed-video decode, actual physical pixels, completion and due-care judgment unresolved. It is a saved diagnostic audit, not the canonical delivery acceptance receipt.

Pinned `runtime.py preflight` passed. The focused suite passed 23 tests, including the independent source join and negative hash/case/adapter checks. Scoped static check exited 0. Exact scoped strict delivery check exited 1 on truthful partial status (`Preparation acceptance failed: partial/missing packages remain`). Commands and log hashes are recorded in `result.json`.

Remaining CPU work: source-bind a reviewed Native site and rider adapter to canonical per-case runners/configurations, compose and fully decode the required video, complete exact offline and positive/negative compatibility and saved processing, write semantic proposals and execution manifest, and test canonical independent delivery/comparison audits. Physical CARLA motion, rider visibility and legal assessment require later original review.

## Original person riding identity join, 2026-11-24

The prior history checked that the bicycle or scooter actor ID stayed consistent but did not join the observed human rider to `site.rider.person_actor_id`. `native_capture.py` now requires the source site's person ID on every original sample before sealing the packet. `cyclist_encounter.audit_original_history` independently checks that person ID through the full 20 Hz history, distinct from the ego vehicle ID. `saved_encounter.finalize_saved` reopens the sealed site and repeats that join, returning the source person ID in its observation. This preserves the statutory “person riding” distinction from the bicycle/scooter vehicle actor. A changed person ID is rejected even if history and packet hashes are recomputed.

Two new negative tests cover a changed rider before acquisition sealing and a resealed changed rider during saved finalization. The full focused suite passes 25 tests (`cpu-rider-person-tests.log`, SHA-256 `87885ee7d2ce7b3e1e862dbbc1275a254734dbfd348181d3be718f68fb501331`). Pinned preflight passes (`cpu-rider-person-preflight.log`, SHA-256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`); scoped static passes (`cpu-rider-person-static.log`, SHA-256 `f64ad44f5d127b586b1fb76505cab0d9d90073885ce063d9098ced2614020366`). Exact scoped strict exits 1 on truthful partial status (`cpu-rider-person-strict.log`, SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`). Commands and hashes are in `result.json`.

Next CPU work remains a source-bound Native rider adapter and runner, six exact bundles, composed source media and full decode, selected-requirement compatibility, semantic proposals/manifest and canonical delivery/comparison acceptance receipts. Physical mounted state and due-care judgment remain subject to later original review.

## Sealed original video composition and saved decode, 2026-11-24

`video_media.py` composes each of the four source-hashed 900-frame PNG archives into lossless 20 Hz FFV1 video without substituting frames. It rejects changed archives and symlink or escaping sources, verifies source dimensions and frame count with FFprobe, fully decodes with FFmpeg, and SHA-seals the four-video manifest. `delivery_audit.audit_saved` now optionally requires an externally supplied video-manifest hash, independently redecodes all four videos and checks exact case/duration before reporting `full_video_decode: true`. Its PNG-only path remains `false`. Small 2×2 CPU fixtures test composition, changed video bytes and changed original archive; no rider visibility or physical/legal acceptance is claimed.

Pinned preflight, 28 focused tests and scoped static passed. Exact scoped strict exited 1 on truthful partial. New SHA-bound logs:

- `cpu-video-preflight.log` SHA256 `97d2c1ffb850c94a84059cef261c8a31cb569a80786f45bd6dc82022c6419e97` exit 0.
- `cpu-video-tests.log` SHA256 `efccc524ac1f9bc038ce2e07b93d0bcdcdb69c27b5ea57e0016a9cb8e98337f6` exit 0.
- `cpu-video-static.log` SHA256 `f64ad44f5d127b586b1fb76505cab0d9d90073885ce063d9098ced2614020366` exit 0.
- `cpu-video-strict.log` SHA256 `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` exit 1.

Remaining CPU work: reviewed Native site and rider adapter, six exact runnable construction bundles, semantic proposals and execution manifest, offline and positive/negative compatibility proofs, and canonical independent delivery/comparison receipts.
