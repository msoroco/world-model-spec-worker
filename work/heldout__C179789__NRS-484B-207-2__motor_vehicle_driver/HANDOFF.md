# Handoff: heldout__C179789__NRS-484B-207-2__motor_vehicle_driver

## Frozen scope

Except when overtaking and passing on the right is permitted, the driver of an overtaken vehicle shall give way to the right in favor of the overtaking vehicle upon observing the overtaking vehicle or hearing a signal. The driver of an overtaken vehicle shall not increase the speed of the vehicle until completely passed by the overtaking vehicle.

Cell C179789: paved_road / travel / other_vehicle; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Overtaken driver’s give-way-right duty after observing overtaking vehicle or hearing signal, except when passing on right is permitted.
- Separate observing and hearing activation paths; compare give-way and no-give-way under fixed overtaking context.
- Overtaken driver may not increase speed until completely passed: compare pre-completion and post-completion speed change, with measured pass completion.

## Current checkpoint

Four cases now separate the rightward-yield clause, no-speed-increase-until-passed clause, and the sourced right-passing exception premise. `overtaken_response.py` measures original speed and right offset after an observed or audible notice and before pass completion. `overtaken_comparison_audit.py` checks the held actor, notice and motion conditions and rejects a missing source binding. CPU tests pass; `cpu-tests.log` SHA256 is `199c77cf3f2c75565ad845489c8a7c6f65ad386d2322ab498befeef5e815c9a1`. No legal conclusion is drawn from the measured deltas.

Status remains partial. Native passing construction, four-camera capture, finalizer integration, three fallbacks per exact case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C179789__NRS-484B-207-2__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C179789__NRS-484B-207-2__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C179789__NRS-484B-207-2__motor_vehicle_driver --complete`. The strict readiness gate still fails while this package is partial.

## 2026-11-17 source-bound measurement restoration

The current worktree lacked `overtaken_response.py` and `overtaken_comparison_audit.py`, so the previously claimed CPU test failed at import. Both modules were authored in this package. The measurement now reads original context/event/motion bytes, binds SHA-256 and paths, checks held participant identities, sourced right-pass exception premise and observed/audible notice, and separates right-shift and pre-completion speed deltas without a legal conclusion. The comparison auditor checks held actor/notice/motion conditions and reopens each source to reject changed bytes. Five CPU tests pass, including the source-tamper negative; `cpu-tests.log` SHA-256 750dbe16ffca0846c1a43aae85a264ca28e2a86df69053048dbba9604d43165a. `.venv-cpu/bin/python worker_check.py --assignment heldout__C179789__NRS-484B-207-2__motor_vehicle_driver --complete` exits 0. Status stays partial. Next: integrate these source-bound functions into exact Native constructions and the four-camera saved-processing path; add three physical-risk fallbacks per selected case and run exact offline/compatibility, delivery and scoped strict proofs.

The case plan now specifies all four named prospective source cameras and maps notice, pass completion, rightward response, speed and right-pass-exception observations to retained original streams. `case-plan.json` SHA-256 a766c13d54d28e0f162085adb87f7833ca5c9e4e29edf83e68713c226f199f2a. This remains a CPU plan; actual visibility and motion are unverified.

The plan now adds exact case `heldout__C179789__NRS-484B-207-2__motor_vehicle_driver__observed_gives_way_holds_speed` and a notice-modality comparison against the audible-signal baseline. The audit also checks the speed-hold comparison. Six CPU tests pass, including speed and notice comparisons and a changed-original-source negative; current `cpu-tests.log` SHA-256 3076db224643f6c069184cc46cc5b790b8e89aca4767e8def0526b0d1d126e6b. These are planning and diagnostic measurements only. Build and prove the new observed-notice construction with the other four cases before readiness.

The full `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` rerun exits 1 at `preparation.py:276`, `Preparation acceptance failed: partial/missing packages remain`; frozen batch inventory remains 44 ready and seven partial. C179789 is one of the partial packages. The return cap is 10,200/10,200 files; any new construction artifacts require lossless consolidation of historical work first.

## 2026-11-17 recomputed-source audit and controller checkpoint

The independent `overtaken_comparison_audit.py` now reopens all original sources and recomputes the entire measurement result through `overtaken_response.py`, rejecting altered source bytes and fabricated scalar values. Its SHA-256 is 0be4f2288eb585cd63fae7ba7471bc8ff81660a29fbd775e1750438a958a5f7f. The new CARLA-lazy `overtaken_controller.py` (SHA-256 75acdc705d5342ba99aab29f2a496b052a61f8bf6603725f7ab816cf76a618ad) defines five exact case target sets, requires a sourced audible or observed notice, keeps the before-completion speed target fixed except in the deliberate speed-increase probe, and exercises `vehicle.apply_control` through a CPU fake. The case plan binds every selected case to that controller and names original notice, pass-completion and right-offset sources; plan SHA-256 86cc23cabef0df27a715307065cdf4e9b0d0c99c59f2466cc050f556f221bf5b. Eight CPU tests pass, including source tamper, fabricated measurement, comparison isolation and controller-call checks; `cpu-tests.log` SHA-256 `67452e0f07c7d3b3a51f4c9de5077b8df782eadbb7b6bae427e3fbe62597f0f4`. CPU preflight and C179789 scoped nonstrict check pass. Status remains partial: implement the Native runner and four camera capture, integrate source readbacks/finalizer, then exact primary and three fallback constructions with offline, compatibility, saved, physical and delivery proofs.
