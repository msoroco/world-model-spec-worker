# testing__C144550__NRS-484B-223-1b__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.223(1)(b) — If a highway has two or more clearly marked lanes for traffic traveling in one direction, vehicles must: Not be moved from that lane until the driver has given the appropriate turn signal and ascertained that such movement can be made with safety.
Assigned branch(es): Both conjunctive prerequisites before lane movement..
Cell: C144550 (one_way_multilane, change_lane, lane_marking); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 3. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 2. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C144550__NRS-484B-223-1b__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 2 exact law/actor ranges. These are unmeasured construction targets. 0 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-23 CPU checkpoint

Added six exact cases: three source-review candidates for frozen accepted IDs and three planned controlled constructions (both observations, signal absent, independent check absent). Two comparisons specify the isolated variable and fixed conditions. No capture is selected or claimed ready. The frozen signal-distance targets include an impossible negative planning target; no legal or physical cutoff is inferred.

`lane_change_timing.py` measures sole-left API onset to first >0.05 m source-lane center displacement by planar original-pose path integral, retaining the sampled departure bracket and source SHA256. It requires original driver-check readback as a separate observation; neither that readback nor surrounding traffic by itself establishes statutory ascertainment. Five focused tests cover positive and missing-signal/check cases, sample gaps and assignment identity.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `d519ccd4c29560db5d2d5fd49a41e667e92059d5ce04d0be45c8b110a6395a97` |
| `lane_change_timing.py` | `6410b14831c1a59226bcbd4a3282c2df138954112e6ada289c393cb3f723d378` |
| `tests/test_lane_change_timing.py` | `71b69eca32058b98d18aacd26e8576c8080986640297d9ae14cb7d31c9b492cc` |
| `preflight.log` | `922701fb8ee7de8a90afe4b900f648f4c1052fcb067399f0107ece0a181251eb` |
| `unittest.log` | `f2ecc91e28dee5ae71c72923031333f99af139436d429cb668e5a9b267567cf1` |
| `static.log` | `f5e364ae41c091e61a0fe5d8910bd685b82f7ed4ae980f43ff9cce974e35793d` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five focused tests exit 0; scoped static exit 0; exact scoped strict exit 1 (`Preparation acceptance failed: partial/missing packages remain`). Log command bindings and hashes are in `result.json`.

Next CPU work: implement real controlled lane-change construction and a capture-backed driver-check source; finalize original signal/lane/traffic packets with source hashes; validate case-specific positive/negative compatibility, delivery and comparison audits. Review accepted original traces/video before deciding whether any new recording is needed. CARLA physical motion and video quality follow CPU readiness.

## 2026-11-24 independent readback finalization checkpoint

Added `finalize_lane_change.py` to bind four independently SHA-sealed original 900-frame packets: frame map, ego pose/lane offset, Native signal readback and driver-check readback. It requires exact case identity and frame/time joins, named lane geometry and distinct signal/check provenance. It feeds the joined rows to the existing source-bound timing measurement without allowing the driver-check packet to override signal state. Negative tests reject stale bytes, missing check provenance and frame substitution; absent observed check stays false. This code does not produce a real driver-check channel or prove ascertainment or safety.

Pinned suite passes 10 tests; preflight and scoped static pass. Exact scoped strict exits 1 on truthful partial. New SHA256 receipts:
- `cpu-independent-readback-tests.log`: `073827435efd36e70550cf9bd8b117d376ca929508b605d7ffd9e74f6e8a7da0`
- `cpu-independent-readback-preflight.log`: `2ab6a3d1f922721f8e39464a6d2bf7cc8d89bbff8a9653437a5c6c16792bcf0a`
- `cpu-independent-readback-static.log`: `f5e364ae41c091e61a0fe5d8910bd685b82f7ed4ae980f43ff9cce974e35793d`
- `cpu-independent-readback-strict.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`

Next CPU work: bind actual original driver-check source, review accepted traces/video, implement controlled lane-change construction and capture, exact semantic proposals, positive/negative compatibility and independent delivery/comparison acceptance.

## 2026-11-25 reviewed-lane construction and independent Native readbacks

`native_construction.py` now checks a SHA-bound independently reviewed highway/map packet before world mutation, requires two distinct clearly marked same-direction driving lanes and paired continuous centerlines, verifies the live OpenDRIVE bytes, and applies route-following vehicle control for `both_observed`, `signal_missing`, and `check_missing`. The control request remains separate from Native API signal readback. `native_readbacks.py` samples 900 contiguous world frames, original ego pose/source-lane offset, `get_light_state` signal state, and a separately sourced original driver-input event with exact frame/time/source ID. It writes four SHA-sealed packets consumed by `finalize_lane_change.py`; a controller request cannot stand in for that readback. The observed event is not proof of mental ascertainment or legal safety.

The two judgment-range below targets in `judgment-probe-plan.json` were corrected from impossible negative path-integral distances to nonnegative 2.0 m planning targets, strictly below the frozen 5.9698483376211176 m minimum. They remain unmeasured physical coverage targets, not legal cutoffs. Six exact plan cases and two controlled comparisons remain fixed.

Sixteen focused tests pass (`proof-native-construction-tests.log`, SHA256 `5037b8546735b8a407f7f957be05648c608c01e24135b71200059f4184e7bf04`), including live map mismatch, wrong-direction/marking rejection, 900-frame saved finalization, altered original source bytes, and a controller-request substitution negative. Scoped static passes (`proof-native-construction-static.log`, SHA256 `f5e364ae41c091e61a0fe5d8910bd685b82f7ed4ae980f43ff9cce974e35793d`). Exact scoped strict remains exit 1 on partial status (`proof-native-construction-strict.log`, SHA256 `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`).

Next CPU actions: implement the owned four-camera 900-frame Native session with capture seal and source retention; materialize the three controlled constructions and decide source-backed reuse for the three accepted candidates; then bind semantic proposals, positive and missing-source compatibility, saved-only processing, and independent delivery/comparison audits to a selected manifest. Original accepted trace/video, reviewed site packet, actual Native motion and physical pixels are absent from this worker export, so no physical or legal acceptance is claimed.

## 2026-11-25 owned Native session and three offline constructions

`native_session.py` now gates reviewed marked same-direction lanes and live OpenDRIVE before mutation, then owns ego and target-lane traffic actors plus four original RGB sensors at 20 Hz. It samples 900 Native ticks, original signal API, independently sourced driver-input event, target traffic position/velocity, PipelineCapture and FrameMap, retaining the four camera PNG sources with frame/timestamp/dimension checks. `media_encode.py` requests four lossless FFV1 views and a synchronized primary. The session destroys all six owned actors/sensors and invokes pinned world restoration with settings/map/weather readback before capture seal. `runner.py` requires both the reviewed map and independent driver-input source and retains their original bytes in the attempt. A driver-input event remains an observation, not proof of legal ascertainment or safe movement.

Three exact current-runtime controlled bundles were materialized under `cases/` with `bundle_builder.py` and passed `runtime.py offline`: `both_observed` `proof-offline-both_observed.log`, `signal_missing` `proof-offline-signal_missing.log`, `check_missing` `proof-offline-check_missing.log`. `manifest.draft.json` binds their construction/log hashes; it is not a selected delivery manifest. Twenty-two focused tests pass (`proof-native-session-tests.log`, SHA256 `bbb826c26a488ec243b4953d684fee92f98e719122bd349da0b5ade1a67d35a0`), including fake-world ownership/restoration, stale sensor timestamp, source substitution, and four-view lossless encoder contract. Scoped static passes (`proof-native-session-static.log`, SHA256 `f5e364ae41c091e61a0fe5d8910bd685b82f7ed4ae980f43ff9cce974e35793d`). Generated media and temporary attempts remain only under `.runtime-work/`.

Next CPU actions remain source-hashed saved-only analysis/recording evidence and physical completion, diagnostic compatibility positive/missing-source proofs, canonical semantic proposals, exact selected manifest, and independent delivery/comparison audits. Existing accepted traces/video are absent; the three accepted-source case IDs stay review candidates pending source review, while the three controlled case IDs are source-gated constructions. No new accepted-recording reuse or physical acceptance is claimed.

## 2026-11-25 saved-source and independent audit checkpoint

Saved-only `analysis.py` now SHA-joins all four independent 900-frame readback packets, retained original driver-input and target-traffic streams, reviewed site, and four original camera PNG streams at the Native frame/time. It emits the exact recording channels and an unresolved legal finding; a separately measured destination-center distance is an engineering completion check, not a safety or statutory cutoff. `comparison_audit.py` tests both declared conjunctive controls against source-hashed reports and identical fixed geometry/traffic/camera context. `delivery_audit.py` requires full video pixel decode and original camera PNG decode, and gates production acceptance on an independent SHA-bound original-source review plus Native exit and owner release. Diagnostic paths cannot claim physical or legal acceptance.

All 28 focused tests pass; three regenerated controlled bundles pass `runtime.py offline`. Scoped static passes. Exact scoped strict remains exit 1 because this package is truthfully partial. Accepted original trace/video and reviewed site are still absent, and their source-review cases are not claimed as constructions.

| Receipt | SHA256 |
| --- | --- |
| `proof-saved-audits-tests.log` | `01ea7eee44c4013a4a8bbc20ff0c42b0539ab98ac1891fb59093274de7a33e1f` |
| `proof-saved-audits-static.log` | `f5e364ae41c091e61a0fe5d8910bd685b82f7ed4ae980f43ff9cce974e35793d` |
| `proof-saved-audits-strict.log` | `fc7782ab1c5e4fd09e7114614b45ca9e0c619d5171e25cd7ce04792fe2f0459c` |
| `proof-offline-both_observed.log` | `3b4a28407c2bc813b2ccdcca4cce6da45b675bc9ad31b7e3e2400650f18f48d7` |
| `proof-offline-signal_missing.log` | `2063c3a380f995751bac4b3fa7067d9c957cdf1e321c946fb0d01c62a94b8960` |
| `proof-offline-check_missing.log` | `065281492d8bcb09efe6cc84ecfa0ebc42c87610eda2007b781f6e22f0c6ce44` |

Remaining CPU work: prove selected saved processing with owner release and negative source cases, positive/negative compatibility for each controlled construction, semantic proposals, risk-tested fallbacks, selected execution manifest, and six-case source disposition. Keep physical and legal status unresolved until original local review.
