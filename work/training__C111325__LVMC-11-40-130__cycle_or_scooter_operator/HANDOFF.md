# training__C111325__LVMC-11-40-130__cycle_or_scooter_operator

Status: **partial CPU implementation checkpoint**. No condition is selected for delivery. No original bicycle execution, physical-condition measurement, or reasonable-and-prudent legal verdict is claimed.

## Source and current construction

Exact law: “It shall be unlawful for any person to operate a bicycle at a speed greater than is reasonable and prudent under the conditions then existing.” The selected witness asks for bicycle speed during a stop-sign intersection approach. The source topics are retained in `case-plan.json`; no accepted recording was present in the frozen local membership snapshot.

`native/speed.py` authors two 600-frame, 20 Hz, 30-second synthetic bicycle approach requests. Both start 50 m before the stop line and stop 2 m before it. The stop sign, visibility, dry road, pedestrian absence, route, and stop line are held fixed. Requested peak approach speeds are 3 and 5 m/s; speed in the proof is recomputed from consecutive positions, not labeled original CARLA velocity. The faster request reaches the common stop position at frame 222 versus frame 337 for the slower request. These speeds are engineering contrast values, not legal thresholds.

`prove-speed-source.py` measured both full traces and rejected six damaged-source or false-authority variants. `native/build_runtime_offline.py` bound frozen law and source hashes into two **unselected** draft constructions. Both pass the current pinned `runtime.py offline` runner under `.runtime-work/c111325/offline-a` and `offline-b`. `audit-speed-current.py` independently joins the frozen law, case plan, source hashes and construction hashes, recomputes speed and stop timing, and checks fixed conditions. Proof and log SHA-256 values are in `result.json`. The assignment-scoped complete checker passed; its strict variant failed on the partial package.

## 2026-11-23 Native setup checkpoint

`native/bicycle_setup.py` provides the proposed `vehicle.bh.crossbike` spawn, exact 600-frame/20 Hz duration, and four source-camera specifications (`overview` 1920x1080; `approach`, `reference_corner`, `driver_reference` 1280x720). It requires a Native route-lane, stop-sign control and approach-clearance survey before spawning; it destroys owned actors on partial spawn failure. Both condition requests share actor spawn, cameras and conditions, varying only requested peak speed (3 versus 5 m/s). This is code for a future Native caller, not evidence that the blueprint is a legally qualifying human-powered bicycle or that the conditions have been measured.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python native/prove_bicycle_setup.py native/bicycle-setup-proof.json` passed against a fake world, including missing-survey rejection, partial-spawn cleanup and comparison-variable isolation. Setup SHA-256 `ee98d0bd57fdc109263de862167f5f71b3fcedd67703f92ec765659dd509f2fb`; proof SHA-256 `ca8f5e49721e3ed74ae92f0e99fb71b306063a8a45eed4eda06cf2450d27cc6f`; log SHA-256 `23016be41a80a8a8d73340151e1187cf64d6e56d09d8d09cc1645caaa6692839`. Pinned `runtime.py preflight` passed. The setup still needs integration with the selected exact capture runner and source-bound saved processing; status stays partial.

## Remaining CPU work

Implement an actual bicycle Native mechanism rather than substituting a motor vehicle; obtain contemporaneous source measurements for speed, visibility, weather/surface, curvature, users and clearance. Provide four synchronized cameras, source-only current compatibility and actual process-saved positive/negative checks, selected case construction and risk candidates, semantic proposals, independent delivery and comparison audits, then rerun the strict scoped gate. Preserve the legal judgment “reasonable and prudent under the conditions then existing” as unresolved; a measured speed or surrogate cannot decide it on its own. Keep this result partial until all CPU preparation proves ready.

## 2026-11-23 four-camera timing diagnostic

`native/prove_camera_sources.py` bound each exact 600-row bicycle request to a video-frame map and four 600-frame FFV1 CPU streams using the camera names in `native/bicycle_setup.py`. All eight diagnostic streams decoded to 600 frames. The source-derived stop frames remain 337 for the 3 m/s request and 222 for the 5 m/s request, with the context and route fixed. Script SHA-256 `a5d04bfbf2427d9942f19fcd95128e51db9db02696ac7bf63e10d19f953b16b4`; returned `four-camera-cpu-proof.json` SHA-256 `ba0419b275af3f093c8ea0cafa83af5aa4d1beb9f920bf60e6227ebb66c3155a`. These 32x32 black software videos do not establish a real bicycle, rider, visible road conditions or prudence finding. Status remains partial.

## 2026-11-25 readback-driven bicycle control

`native/bicycle_control.py` now issues bounded `VehicleControl` throttle/brake from live bicycle position and velocity readbacks for the two exact 3 and 5 m/s engineering requests. It rejects a wrong blueprint, nonfinite source, reversed or teleported travel, lateral departure and crossing beyond the common stop position. These values guide an original capture and do not establish realized speed or legal prudence. `native/prove_bicycle_control.py` passed two condition checks and five negative checks against a fake Native actor. The proof and exact hashes are in `result.json`. The controller is still separate from a selected capture runner and original saved-source audit, so this remains partial.

## 2026-11-25 independent original-speed audit

`native/audit_original_speed.py` independently checks 600 original bicycle actor rows against the four-camera frame map, Native actor identity, monotonic timing, finite poses and velocities, fixed conditions, approach lane, complete stop and the measured speed/timing contrast. It leaves the statutory prudence judgment unresolved. `native/prove_original_speed_audit.py` passed two mock condition traces, the controlled comparison and five negative checks: synthetic-as-original, switched actor, broken camera join, altered fixed conditions and stop overrun. Proof and hashes are in `result.json`. The mock traces are temporary in `.runtime-work/`; no original CARLA observations or source pixels are asserted. The selected capture runner and full delivery package still need construction.

## 2026-11-25 stop-sign and lane alignment

`native/build_speed_road.py` rotates a source-hashed C111325 stop-sign intersection OpenDRIVE map into the speed request's x-axis. Its CPU geometry proof verifies the governed incoming road, driving lane, sign at x=0, crosswalk at x=3, 50 m bicycle approach and stop at x=-2. The bicycle center now follows lane y=-1.75 m in both 600-frame diagnostic traces, setup and independent audit. Source proof, independent audit, both current-runtime offline constructions, four-camera timing, mock Native setup and controller/audit checks were rerun after that change; hashes are in `result.json`. This map geometry remains a CPU construction proposal until original Native map readback and physical review. Selected delivery binding and public/saved/semantic/delivery proofs remain.

## 2026-11-25 original route survey

`native/survey.py` fails closed unless the original CARLA map readback exposes road 1, stop signal 901 at x=0 and three bicycle approach waypoints on driving lane -1 centered near y=-1.75. It records original weather precipitation and wetness without treating them as verified visibility or legal conditions. `native/prove_survey.py` passed the source-map CPU fixture and rejected wrong lane, shifted sign and wrong sign type. This still needs integration into the selected capture runner, a reviewed bicycle classification and original pixels.

## 2026-11-25 original capture path

`native/live_capture.py` connects the source-hashed road, original route survey, bicycle setup and readback-driven controller to a prospective exclusive CARLA run. It records 600 original bicycle pose/velocity rows, Native frame identities, four synchronized original camera streams and raw frame/source hashes. It uses the shared frame writer and restores the operator-owned world with cleanup in `finally`. Its CPU construction check passed; no CARLA server was contacted. Saved finalization, physical status assessment, selected execution-manifest binding, public compatibility, recorded-only processing, semantic proposals and independent delivery proofs remain incomplete.

## 2026-11-25 selected proposal checkpoint

`proposals/cases.json` now names the two exact selected bicycle-speed conditions, assigns the statutory text and reviewed stop-sign approach topic to both, and declares the 600-frame measured-source channels. `case-plan.json` maps every original observation term to its proposed channel and retains unverified physical conditions and legal judgment. The unselected offline drafts were rebound to this plan and both passed current-runtime offline again. This is a selected planning checkpoint, not a selected executable delivery manifest; public compatibility, recorded-only saved processing and full delivery checks remain CPU work.
