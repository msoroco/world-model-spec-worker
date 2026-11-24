# training__C213851__LVMC-11-20-060__motor_vehicle_driver

Status: partial. The two road-to-driveway attempts are draft definitions, not selected delivery cases. No Native execution, physical observation, legal verdict or accepted recording is claimed.

## Source and branch scope

The frozen law is LVMC 11.20.060, and the catalog cell is `residence_district / exit_road / driveway_entrance` for a motor-vehicle driver. The witness describes road exit into a private driveway across a sidewalk, with a separate pedestrian. No accepted full-train membership is listed. The first case-plan wording implied the subject later entered the roadway; I corrected both cases and the comparison to retain the road-to-driveway direction. The statute's separate “upon entering the roadway” duty is therefore not proved by this cell. That branch needs a compatible roadway-entry cell and its own controlled cases.

## New CPU construction and checks

`build-semantic-foundation.py` authors and validates pinned relevance, exact law template, three value-free judgment-observable contracts, and bindings. `build-canonical-cases.py` validates a neutral baseline and the two controlled sidewalk-stop-policy attempts against the pinned cases stage. Both attempts hold geometry, district context, pedestrian route, traffic context, approach speed, turn path and recording profile fixed; only `commanded_stop_policy` changes. The recording contract retains full frame-joined ego pose, speed, footprint, pedestrian motion, roadway traffic and source-verified geometry for a 30-second or longer capture. Three judgment sweeps remain explicitly incomplete because physical ranges and compatible roadway-entry geometry are unverified. These are source-bound draft definitions, not construction or compatibility receipts.

Commands run with `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/owner-c213851`:

- `.venv-cpu/bin/python runtime.py preflight` — exit 0.
- `.venv-cpu/bin/python work/training__C213851__LVMC-11-20-060__motor_vehicle_driver/build-semantic-foundation.py` — exit 0; seven draft semantic stage validations.
- `.venv-cpu/bin/python work/training__C213851__LVMC-11-20-060__motor_vehicle_driver/build-canonical-cases.py` — exit 0; cases stage validates 3 draft cases and 3 incomplete judgment sweeps.
- `.venv-cpu/bin/python worker_check.py --assignment training__C213851__LVMC-11-20-060__motor_vehicle_driver --complete` — exit 0 static checkpoint exit 0 after final edits; static checkpoint only.
- `.venv-cpu/bin/python worker_check.py --assignment training__C213851__LVMC-11-20-060__motor_vehicle_driver --complete --require-delivery-ready` — exit 1, `Preparation acceptance failed: partial/missing packages remain`; status is truthfully partial.

Proof files and logs:

- `assignment-static-check.log` SHA-256 `5867a3746284dbb600d14044e5889a952b195d9deefd7c65354a2f84297bbe35`
- `cpu-preflight.log` SHA-256 `5929cfc751f06630ee9c7966b7a90a9c6e5ffab5ed7995b42a7efda2cf60ab3e`
- `semantic-foundation-validation.log` SHA-256 `a6d5e7f20904ac6c8a3cb40c933bbf305954a1b8c124e828efd8ea69f9bea4f1`
- `semantic-cases-validation.log` SHA-256 `eb14ee5e92094a080198173df1604806837822745e93a74601c706057ae05b79`
- `assignment-strict-gate.log` SHA-256 `4b7c473100b0567da2a85548669f3b674e506ee243d68a01763fb24c3c8a61e2`
- `proposals/semantic-foundation-proof.json` SHA-256 `a0bd8c0562f893368d7aa10340c16d9ac22254d464c1f9628248cbf9b4ae4265`
- `proposals/semantic-index.json` SHA-256 `bd3fc81de9800e0fe7e86acd72cb70eaa978ac10021bd130a7c18eccae4f0191`
- `proposals/cases.json` SHA-256 `3f3502903f2be52e9d1d514f2e3d439e24003cc9a7450a3de8836b4fd3b39db2`

## Remaining worker-owned CPU work

1. Source-verify the sidewalk polygon, connected road-to-private-driveway route, residence-district context and separate pedestrian route; construct the exact Native scene and controller for both attempted stop policies without asserting a legal cutoff.
2. Implement the frame-joined 20 Hz source capture, all four required source-camera streams, measured stop/footprint/pedestrian outputs and saved-only finalizer. Run the primary offline, positive and missing-source negative compatibility path and saved-processing path.
3. Construct and test three distinct risk-triggered fallbacks per selected case, then run exact comparison and independent acceptance audits against the final construction. Freeze physically justified sweep ranges for the two applicable judgments; handle the roadway-entry branch in a compatible cell.
4. Run the assignment-scoped strict gate again. Promote to ready only after it exits 0. CARLA execution and physical review remain local operator work after CPU preparation.
