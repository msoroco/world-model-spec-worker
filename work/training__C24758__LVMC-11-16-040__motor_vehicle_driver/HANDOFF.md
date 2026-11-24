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
