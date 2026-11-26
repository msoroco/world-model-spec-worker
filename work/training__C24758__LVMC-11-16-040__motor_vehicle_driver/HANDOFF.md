# training__C24758__LVMC-11-16-040__motor_vehicle_driver

Status: partial. No delivery recording is selected or claimed.

## Source review

Law: LVMC 11.16.040. Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 0}. No accepted equivalence receipt was verified.

## Planned controlled comparison

speed around 15 mph after verifying both 100 ft sight segments. Compare only `observed_speed_in_sight_limited_intersection` (mph) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 2 case definitions are unselected and have no observed values.

## Incomplete CPU work and resumption

Executable Native package and all four candidate offline/compatibility proofs absent; exact statutory exceptions and historical equivalence remain unverified. Build and validate semantic stages, exact Native construction, four distinct candidates per selected case, full mandatory capture, saved positive/negative fixtures, independent audits, and comparison audit. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.

Update 016 status correction: missing construction, cases, proofs and audits are actionable CPU work under START_HERE.md, so this assignment is partial rather than externally blocked. Existing scope, plan and next actions are retained.

## 2026-11-23 source-bound sight and speed CPU construction

`native/sight_speed_measure.py` is a saved-source diagnostic for the exact selected sight-conditioned branch. It requires 600 consecutive 20 Hz frames, approach coverage from 100 ft to the intersection boundary, a sight record for the intersection and every inventoried entering approach at each sampled last-100-ft frame, explicit reviewed negative evidence for both statutory exceptions, and speed samples during traversal. It reports sight-limited frame counts and observed traversal speed in mph against the statutory 15 mph reference. The legal verdict remains null. The source hash is required at invocation. `native/sight-speed-contract.json` records source requirements and unresolved legal interpretation.

Synthetic CPU proof command: `TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C24758__LVMC-11-16-040__motor_vehicle_driver/native/prove_sight_speed_measure.py`; exit 0. It ran paired 600-frame/20-Hz diagnostics at 13.869 and 16.106 mph and rejected five negatives: changed source hash, unresolved through-street context, a missing entering approach view, bad frame/time join and short capture. Synthetic values are diagnostic, not Native observation.

Scoped checkpoint: `TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c24758-output .venv-cpu/bin/python worker_check.py --assignment training__C24758__LVMC-11-16-040__motor_vehicle_driver --complete`; exit 0, static checks passed.

Hashes (SHA-256):

- `native/sight_speed_measure.py`: `a455704e03b30897991c15a30171021a99e50ade1b6ee9c2a9a2a2aa85575f7a`
- `native/prove_sight_speed_measure.py`: `6b95bb1f1e584959ee3e05c04cec151e1047dc62636fe20d08cb0d8ef4b2e818`
- `native/sight-speed-contract.json`: `a3bff8d8043fedaeb2130b8ddbd0cdfb127c5e4baf96ae4a64b06fa7f2388cb9`
- `native/sight-speed-proof.log`: `6c6e96868ad32ed24d1a76b66990464515060a6c52d65ceb8e76d23b15342b2a`
- `native/scoped-complete.log`: `27225865bdc38502505d4255e5ede4fee8837b0c546e16b8d787dfc98ccc3cf1`

Remaining CPU work: construct exact CARLA/Native primary and risk-based candidates for both selected cases; capture independent 100-ft sight and every entering-road traffic source with four cameras; bind saved-only finalization and conversion; run pinned offline, positive/negative compatibility, saved-processing, delivery audit and comparison audit. Review original-source visibility and both exception facts before claiming the branch active. Physical and legal outcomes remain unknown.

## 2026-11-23 exact reference primary integration

`native/draft-primary-manifest.json` binds `native/primary-construction.json` for exact reference case. `native/runner.py --check` validates its 30-second, 20 Hz, four-camera config. `native/runner.py --output-dir ... --host ... --port ...` delegates to `native/native_capture.py`, which uses an exclusive idle CARLA world, selects a junction approach, records the original map OpenDRIVE hash, entering driving lane geometry, nearby traffic-signal actors, 600 Native ego pose/velocity/controller samples, four synchronized original RGB camera streams with per-frame pixel hashes, and a FrameMap. It snapshots/restores the world and records errors. This Native branch is CPU-parse/offline tested only; no CARLA run occurred. Its straight-steer controller, selected junction and camera framing need physical review.

`native/saved_source.py` joins an exact saved case, 600-frame FrameMap, four byte-hashed and decoded 20 Hz camera videos, and the source-bound sight/speed observation. Synthetic 4 x 600-frame media are generated only under `.runtime-work/`. The saved-source proof has four negative checks: altered camera bytes, stale FrameMap hash, altered Native frame identity and missing camera. The sight/speed proof has five additional negatives. No physical or legal claim is made.

Pinned command: `TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c24758-output .venv-cpu/bin/python runtime.py offline --manifest work/training__C24758__LVMC-11-16-040__motor_vehicle_driver/native/draft-primary-manifest.json --case training__C24758__LVMC-11-16-040__motor_vehicle_driver__reference --output $PWD/.runtime-work/c24758-primary-offline-native-v3-20261123 --python $PWD/.venv-cpu/bin/python`; exit 0, 4 offline tests pass, simulation_started false.

Exact integration gap: Native acquisition currently saves raw map, ego and camera sources but cannot create the required independently reviewed per-frame intersection/entering-road visibility and both negative exception facts. `saved_source.py` therefore cannot finalize a real Native attempt without that source review; its synthetic proof tests software joining only. Full `runtime.py process-saved` additionally needs a selected execution manifest, Native exit/owner release, Core conversion inputs/validator, positive/negative compatibility and independent delivery audit, none yet bound. Contrast and candidates remain unconstructed.

SHA-256 bindings:

- `native/runner.py`: `a28fd0672cd924b4290351f6606efb2da4c4b8f26a8a0b98d99d91e38efd3535`
- `native/native_capture.py`: `4adf5899e47df9b8448f22b3420aaef78803ddc813ad68d823f12a84ed4867a0`
- `native/saved_source.py`: `7be151ac6c2458524384190bd69c36e3cfac67ae7c12bd60885c2794a2c954c5`
- `native/config.json`: `46b330c97406933edec1b65e03c4df0f51e34bf7c831079f8424b8490491e88b`
- `native/primary-construction.json`: `238e3f55eacabc12e868f8f0b7a27c0e7b162d701d7c98cba83752227e4c688a`
- `native/draft-primary-manifest.json`: `09b7db00c9d35577fb4a9b015c123de67966389ae48d91db0a6d8b43b7fba6e4`
- `native/primary-offline.log`: `723f9cda48391b804380648111d967ecb53b7ad4bed64879f32225c1b886ea51`
- `native/saved-source-proof.log`: `217e075a8eba403857880c65966c2d1ac0e5bb5849a8e448fd901c03db27de6b`

## 2026-11-25 paired Native drafts and original sight-ray inventory

Pinned CPU preflight passed with the installed environment. The draft reference and contrast bundles now share the same 30-second, 20 Hz, four-camera capture and controller. The requested speed alone changes from 6.2 to 7.2 m/s. `native/runner.py` checks the exact case and target-speed pair, while `native/saved_source.py` accepts the exact case supplied by the runner. Both draft constructions passed pinned `runtime.py offline` with four tests each, including a 600-frame saved-media join and fail-closed source negatives. The reference and contrast construction SHA-256 values are `2fe01062071e40b4c5a0a5c7614267a578257757ddccd395517f144b45f2e42a` and `b366c2fb88b70b762d7accd2cd0cc73e2379f6d947bba38b0038b62006f83379`. Their returned proof logs are `native/reference-offline-20261125.log` and `native/contrast-offline-20261125.log` (SHA-256 `c6460015937fbad462f511a445199c1b92feff9665b4b46ca95865d9db0dd844` and `f3e51a9b7cad90ae184ba1ace179454f2cce01efb905b371c6a35245f69f3c15`). No CARLA simulation ran.

`native/ray_inventory.py` now records original Native ray hits from the driver-eye position to the intersection and 0, 50 and 100-foot points on every inventoried entering driving lane for each capture frame. The offline CPU test checks the complete target inventory, ray source values and rejection of ambiguous entering-lane geometry. Raw ray hits are preserved for independent review; no Boolean visibility or statutory exception result is asserted from them. The map priority, traffic-control and traffic-visibility reviews still need source-bound construction before a real saved attempt can finalize.

Status remains partial: selected delivery manifests and current-runtime public positive/missing-source negative, recorded-only saved, semantic, physical, delivery and comparison proofs are not yet bound. The next CPU step is to turn the ray, map and four-camera readbacks into reviewed source packets with exact hashes, then bind both cases into selected manifests and run the full proof chain. The draft logs demonstrate software joining only, not physical realization or legal acceptance.

`native/context_review.py` now provides that source-packet assembly interface. It requires hashes of the original FrameMap, Native ego readback, original OpenDRIVE and context, a named reviewer and method, per-frame ray and original RGB pixel hash bindings, reviewed visibility for the intersection and every entering approach, and separate reviewed negative facts for the through-street and traffic-controlled exceptions. It emits a source-hashed observation and invokes `sight_speed_measure.measure`. The pinned offline test uses synthetic sources to pass a 600-frame join and rejects a changed sight-ray hash. It proves the joining logic only; actual review facts must come from original Native captures. Native speed readback is now sampled after the same world tick as pose and camera frames.

After these changes, the final reference and contrast draft construction SHA-256 values are `5757b830ba7cef2d6dfa78fdda0cde0ec67f3f18678f6b0dfeb954c929fbc43f` and `1a57d68e3cd4e894701c3f6a7462e9196298653733f1271f48896661f2aaae94`. Both pinned offline commands passed five tests, with returned logs `native/reference-offline-final-20261125.log` (SHA-256 `0420280ca9fc572bfd383dd19abc40c5ea79aea0225cbb95bafb146c62bbdc0b`) and `native/contrast-offline-final-20261125.log` (SHA-256 `e91e3e74fbbdb1ca0b341a59c2e835081b5d1ee4efc385e5586d8704a4116e25`). The earlier draft construction hashes above are historical checkpoints, not the current selected hashes.
