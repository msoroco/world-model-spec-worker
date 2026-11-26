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
3. Assess each selected case for a concrete physical risk; use no fallback if none is justified, or one or two tested fallbacks with a measurable trigger. Run exact comparison and independent acceptance audits against the selected construction. Freeze physically justified sweep ranges for the applicable judgments; handle the roadway-entry branch through a separately reviewed compatible allocation.
4. Run the assignment-scoped strict gate again. Promote to ready only after it exits 0. CARLA execution and physical review remain local operator work after CPU preparation.

## 2026-11-26 source-shaped road-exit CPU work

`native/measure_sidewalk.py` now requires a sealed original Native source set: reviewed road and site geometry, exactly 600 joined 20 Hz vehicle and pedestrian rows, and four synchronized camera identities. It measures first observed vehicle-body sidewalk crossing, pre-sidewalk stopped frames, and minimum vehicle-pedestrian center distance without defining an immediately-prior legal cutoff or collision-necessity threshold. Its Native/Core join requires matching trace and capture rows. The meter rejects missing or changed original sources, missing Core sources, Boolean speed and broken camera frame joins. Its source-shaped fixture is diagnostic only and does not claim original Native capture, a district legal determination, actual pixel review or a verdict. `native/prove_sidewalk.py` passed two stop-policy positives and ten negatives; `native/sidewalk-source-shape-proof.json` SHA-256 `8209905fd70f4c36a28dc307252b6393d2d180b03ea9d56739a14fc99355d2bf`.

`native/audit_comparison.py` independently re-measures both exact cases and holds road/site hashes, pedestrian route, actor identities and capture times fixed while requiring a changed observed stop-policy response. `native/prove_comparison.py` passed one source-shaped pair and rejected changed site and pedestrian contexts; `native/sidewalk-comparison-proof.json` SHA-256 `2cdac716f7310dabbb6c39078ce5b4fa9a34073013f1a7007edf517d750b6071`. `native/finalize.py` is authored for saved-only Native/Core frame joins and keeps physical and legal acceptance false; it is not yet bundled or exercised through public compatibility. Both proof commands use `TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -B work/training__C213851__LVMC-11-20-060__motor_vehicle_driver/native/prove_sidewalk.py` or `prove_comparison.py`. The scoped `worker_check.py --assignment training__C213851__LVMC-11-20-060__motor_vehicle_driver --complete` still passes with status partial.

The frozen `inputs/coverage/candidate-cells.json` contains no actor-eligible candidate for the distinct upon-entering-roadway duty: the known `enter_road` rows C62266, C62301 and C195651 do not list `motor_vehicle_driver` as an eligible ego party. Keep that clause pending a reviewed scope allocation; do not misrepresent this road-exit pair as roadway-entry yield. Worker-owned next steps are the exact Native road/driveway construction and capture runner, selected offline and public positive/missing-source compatibility, recorded-only process-saved proof, physical and independent delivery audits, and a strict scoped gate. This package is not ready.

`native/build_requests.py` now materializes 600 exact 20 Hz controller targets for each road-exit case, with identical pedestrian path, timing, roadway-traffic observation policy, sidewalk interval and legal context. `native/check_requests.py` independently verifies both complete timelines and their fixed-versus-different fields. `native/prove_requests.py` passes the pair and rejects changed pedestrian and site-review requirements. `native/request-proof.json` SHA-256 `c4886a3719a139412e403e5ba726ad9c075aec29aed79b3b078e122658bfa598`. These are requested controller targets, not Native results or selected delivery. Next bind a physically plausible authored OpenDRIVE road, actual connected driveway/sidewalk geometry and prospective capture runner to the exact two construction bundles, then run the public and saved proof chain.

The prospective `native/road/road.xodr` now authors a two-direction residence road, right-side 2.0 m sidewalk lane and a private-driveway driving surface intersecting that sidewalk at the authored crossing. `native/check_road.py` parses and verifies the source-shaped OpenDRIVE geometry, lane types, widths, driveway orientation and geometric crossing; road SHA-256 `57aa2274b1241f2e98da144233745c1f0e1d5262a4673c037d53fed8609023c2`. This proves authored geometry only. Native junction topology, driveability, mesh quality, legal private ownership, district applicability and sidewalk visibility require local execution and original review. The runner must test the real map and fail if the driveway/sidewalk connection is absent; geometry should not be inferred from the textual label alone.

## 2026-11-26 exact bundle and saved finalizer progress

Both exact primary cases now have inline construction bundles at `native/stop_before_sidewalk/construction.json` and `native/cross_without_stop/construction.json`. The bundle contains a prospective Native entrypoint, four exact camera specifications, 600 requested frames, the authored road and independent request/road checks. `native/probe-offline-manifest.json` is a diagnostic dispatch manifest only. Both cases passed the current `runtime.py offline` command with the pinned CPU Python, each running the entrypoint's CARLA-free `--check` and two bundle tests. The receipts in `native/probe-offline-proof.json` bind construction and log hashes. No CARLA simulation, actual roadway connection or original pixels were observed. The selected delivery manifest and public compatibility are pending.

The meter now seals `original-site-review.json` plus four relative `site-sources/*.json` originals along with Native rows and four camera identities. The source-shaped proof passes two cases and rejects ten changed/missing source or frame-join tests. `native/prove_finalize.py` materializes the exact bundled finalizer for each case, passes saved-only source-shaped positive processing and rejects a missing original sidewalk source for each. The proof is `native/finalizer-source-shape-proof.json`; its source-shaped fixtures do not establish physical or legal acceptance.

Next CPU steps are public compatibility with selected measurement contracts and source-negative recipes, recorded-only process-saved lifecycle checks, and independent delivery and comparison audits bound into the canonical execution manifest. The distinct upon-entering-roadway clause remains pending a compatible actor-eligible cell allocation; the frozen candidate catalog supplies none. Keep result status partial and rerun the exact scoped strict gate after those proofs.
