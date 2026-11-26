# training__C230247__NRS-484B-307-12a__motor_vehicle_driver

Status: partial. NRS 484B.307(12)(a) grants a driver facing a downward green arrow permission to drive in a lane over which it is shown. It does not itself prohibit a different lane; the red-X duty belongs to a separate assignment. The frozen membership has no accepted recordings, so neither exact case has a source-backed reuse.

## Current CPU checkpoint

Two exact unselected drafts compare travel in the lane governed by the green arrow with travel in the adjacent lane, holding the two-lane road, signal location, direction, actor, 20 Hz, 30-second duration, and four-camera plan fixed. `native/road.xodr` provides the two 3.5 m driving lanes and an overhead dynamic signal proposal. `draft-manifest.json` binds current runtime source-manifest SHA-256 `5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3`.

- `draft-same_lane/construction.json` SHA-256 `ede501a0d45b17bbe02ea1ca91acf9d1bb6518ae5005cd548a06560f5f408154`; current-runtime offline log SHA-256 `43d3415fffba8337d957356dd1b31dc27ace0c846dbeb955dd9adb94e97d4769`.
- `draft-other_lane/construction.json` SHA-256 `b9181290b2dcc1fc4a99db43de71f032952c9c2e7689a2ecde4e70f9d7eb5a61`; current-runtime offline log SHA-256 `1823537a168a1416bddbb8325d47ac17255e9d528d96afc14e634b6317dfbc57`.
- `native/draft_runner.py` now forms the same nested original post-tick source rows that `native/lane_arrow_meter.py` consumes. It rejects an unverified original map signal inventory, mismatched state-to-signal IDs, missing actor body vertices and absent proposed lane. The meter joins arbitrary consecutive original Native frame identities and 20 Hz times, checks exact lane-arrow state and map provenance, and requires all eight body vertices in the reported authored lane. `native/prove_lane_arrow.py` runs positive and missing-source, red-X, direction, adjacent-lane and body-straddle negatives; its log SHA-256 is `55cffd89e0be8e20df972891db3cea06a3d1576762f0dfd177a169856dd974dd`. These are software fixtures and make no physical or legal claim.

## Exact remaining work

The two drafts are unselected. `native/signal_source.py` now fails closed on original map identity, governed lane, dynamic overhead geometry, exact Native lane-control actor role and state; it rejects generic traffic-light Green. Wire it to moving actor capture with all four synchronized cameras and original FrameMap, source-bound saved finalizer, exact selected construction and measurement contracts, public offline and compatibility positive/negative receipts, semantic proposals, physical/lifecycle tests and independent delivery/comparison audits. Add a fallback only for a concrete physical risk and prove it. Run the scoped strict gate before changing `result.json` to ready:

`TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c230247 .venv-cpu/bin/python -B worker_check.py --assignment training__C230247__NRS-484B-307-12a__motor_vehicle_driver --complete --require-delivery-ready`

The currently partial strict gate exits 1 with `Preparation acceptance failed: partial/missing packages remain`. Actual indication, official device provenance, lane motion and video pixels remain local physical checks after CPU preparation. The authored OpenDRIVE signal is a proposal, not proof that CARLA shows an official green arrow.
