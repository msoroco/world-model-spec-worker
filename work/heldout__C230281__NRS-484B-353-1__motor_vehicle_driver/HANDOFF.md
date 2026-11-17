# Handoff: heldout__C230281__NRS-484B-353-1__motor_vehicle_driver

## Frozen scope

Except as otherwise provided in subsection 2, the driver of any vehicle, when meeting or overtaking, from either direction, any school bus, equipped with signs and signals required by law, which has stopped to receive or discharge any pupil and is displaying a flashing red light signal visible from the front and rear, shall bring the vehicle to an immediate stop and shall not attempt to overtake or proceed past the school bus until the flashing red signal ceases operation. The driver of a vehicle upon a divided highway need not stop upon meeting or passing a school bus which is positioned in the other roadway. The driver of a vehicle need not stop upon meeting or passing a school bus where traffic is controlled by a traffic officer.

Cell C230281: road / travel / school_bus; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Active flashing red front/rear, properly equipped stopped school bus receiving/discharging pupil: meeting and overtaking from both directions; compare stop and pass.
- Temporal prohibition on proceeding past bus until flashing red ceases: compare hold until off and early proceed.
- Exception: divided highway, bus in other roadway.
- Exception: traffic officer controls traffic.
- Visible lights, pupil purpose and bus equipment role have distinct measured and declared evidence needs.

## Current checkpoint

Eight planned cases cover meeting and overtaking approaches from either direction, stop versus pass during the flashing-red interval, restart while red remains active, the divided-highway other-roadway and traffic-officer exceptions, and motion after red cessation. The new exact case is `heldout__C230281__NRS-484B-353-1__motor_vehicle_driver__meeting_restart_before_red_ceases`; comparison `premature_restart_during_red` holds the red interval, stop frame, bus, subject, approach and pass state fixed against `meeting_stop`. `school_bus_response.py` now measures original red-onset-to-first-stop latency, first pass transition, premature restart after a stop, and continuous hold until cessation, with SHA-256 bindings to the original context, signal and motion files. It requires an original frame rate, frames at both signal transitions, finite speeds and an unpassed bus at onset; no legal reaction-time threshold is asserted. `school_bus_comparison_audit.py` independently checks timing consistency, fixed original signal/context hashes and the new comparison variable. Nine CPU tests cover both approach directions, early restart, pass transition, fixed-condition changes and missing/contradictory sources; `cpu-tests.log` SHA256 is `815272e88cd5a704e6f0b33b60952f83625d6e54c5e197bf90b9164a76527cdb`.

Status remains partial. No legal or physical acceptance is inferred. Exact Native construction, four-camera capture, finalizer integration, three fallbacks per case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Finish the full-text source/reuse mapping for the eight planned exact cases, preserving the accepted non-pupil-purpose branch and avoiding any invented numeric cutoff for "immediate". Bind original source identities to each required observation.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C230281__NRS-484B-353-1__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C230281__NRS-484B-353-1__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C230281__NRS-484B-353-1__motor_vehicle_driver --complete`. Strict readiness still fails while this package is partial.

## Latest gate outcome

After the nine-test temporal-source change, `.venv-cpu/bin/python runtime.py preflight` exited 0 and `.venv-cpu/bin/python worker_check.py --assignment heldout__C230281__NRS-484B-353-1__motor_vehicle_driver --complete` exited 0. The full `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at `runtime/scenario_pipeline/worker_exchange/preparation.py:276` with `Preparation acceptance failed: partial/missing packages remain`; `work/_shared/strict-gate-latest.log` SHA256 is `8a5196a775b4e25dcc5ad430d9aa36835506a570dd5afd41ee669c3da366a69e`. Effective inventory is 40 ready and 13 partial of 53, including two supplemental branch bindings. The return is 10,200/10,200 files. This package is partial because the exact construction/proof/audit chain listed above remains worker-owned CPU work.

## 2026-11-17 restored source measurement, construction control and motion comparison

This section supersedes the stale nine-test/current-file claims above. The previously described source and comparison files were absent from the returned package at this checkpoint; their exact historical bytes remain in the `preserved_source_artifacts` entry of `result.json`, but are not current executable files. The active package now has `school_bus_response.py` SHA-256 `2ce67fdeb954983cf8e4ed3bb8cf68bd022ab3ad296a17de06bb610fb86837d1`, `school_bus_controller.py` SHA-256 `a8367a8a30e79faa4584ecea8342a1ff6fb5b50935c715bc17ddd2546fe65d87` and six passing CPU tests in `cpu-tests.log` SHA-256 `08d590b2fefb052cf1a6d4474bec5cca5c45fc1bfd109df71b22122388d349bf`. The response opens and hashes original bus context, signal and subject/body motion, joins frame/time/identity, checks the front/rear flashing phase, computes full-body signed gap in the travel direction, first stop, early restart and pass during red. A 0.05 m/s stop tolerance is measurement noise, not a legal time or speed threshold. The construction controller covers the eight planned branches and calls vehicle control. The independent motion comparison reopens both original source sets and rejects a changed bus context/signal, missing source, absent held-stop baseline or missing declared early restart/pass difference. It does not make a physical or legal acceptance claim.

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/heldout__C230281__NRS-484B-353-1__motor_vehicle_driver/tests -v`; six tests pass. Pinned preflight and `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment heldout__C230281__NRS-484B-353-1__motor_vehicle_driver --complete` exit 0. Status remains **partial**. The exact next CPU work is an executable CARLA-lazy runner and four-camera acquisition, one selected complete saved path, case-specific source/measurement contracts, three distinct tested risk-triggered fallback constructions per selected case, exact offline and positive/missing-source compatibility, current saved processing, canonical semantic proposals, and independent delivery/exception audits. Rerun proofs after each construction/finalizer change and require the scoped strict gate before readiness. These are worker-owned unfinished tasks, not environment blockers. No actual CARLA recording or legal conclusion is claimed; no frozen input, runtime, batch or Git action changed.

Current scoped strict `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment heldout__C230281__NRS-484B-353-1__motor_vehicle_driver --complete --require-delivery-ready` exits 1 at `preparation.py:276` because status is partial. The stable-tree full strict retry with a 180-second limit timed out with no output (exit 124; ignored `.runtime-work/full-strict-native-exit-schoolbus-20261117.log` empty, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`). Neither outcome establishes readiness. The last completed full strict verdict is the partial/missing-packages assertion. Continue the exact CPU construction/proof steps above.

## 2026-11-17 Native actor motion readback continuation

After the six-test checkpoint, `school_bus_controller.py` gained `motion_readback(subject, bus, travel_tangent_xy, frame, time_s)`. It opens actor transforms, world bounding-box vertices and subject velocity to produce an original motion row with actual subject/bus identity, four lower body corners, speed and travel tangent. It rejects missing vertices, nonfinite values and invalid tangent/frame; this is a CARLA-lazy adapter and was tested with fake actor readbacks in both tangent directions, not a Native capture. Current controller SHA-256 `6f78936177f275f30da8a44fc9a642192db65d40b043a3a5b7d7172013ef2373`; seven tests pass in `cpu-tests.log` SHA-256 `3f6413372a6d3a6596e670d31022d2edf9c93271f83e2e97ac7a780ed5a9255f`; `result.json` SHA-256 `6b15cd54e6e9f3b94f56c94798751dc63258860b5373f1530631419d632b6678` remains partial. The C230281 scoped nonstrict `worker_check.py --complete` still exits 0 after this change. Next wire this readback into a selected exact Native runner and four-camera source acquisition, then complete the source/receipt path listed above. The prior full strict timeout occurred before this readback addition and is not a post-change full-batch verdict.

Independent case-plan review found that `premature_restart_during_red` holds the **no-pass during red** state fixed. The motion audit now rejects an early restart variant that also passes the bus before red cessation; its seven-test suite covers that negative. Current `school_bus_response.py` SHA-256 `fabbf3dba6f62a31550ce7ef60539029c13d8aa572cc51d86f364eae344b01f9`. The test log and result hashes remain as recorded in the immediately preceding section because the passing test names/count and result metadata did not change. This still is a partial package: no source acquisition or exact saved delivery path yet.
