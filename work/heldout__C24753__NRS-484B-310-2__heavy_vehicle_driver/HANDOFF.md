# Handoff: heldout__C24753__NRS-484B-310-2__heavy_vehicle_driver

## Frozen scope

Whenever an illuminated flashing red or yellow signal is used in conjunction with an official traffic-control device, it shall require obedience by vehicular traffic as follows: When a yellow lens is illuminated with rapid intermittent flashes, drivers of vehicles may proceed past such signal and through the intersection or other hazardous location only with caution.

Cell C24753: blind_intersection / travel / flashing_yellow_signal; actor heavy_vehicle_driver.

## Full-text branch inventory for CPU construction

- Rapid intermittently flashing yellow lens used with official traffic-control device at intersection or hazardous location.
- Proceeding past signal is allowed only with caution; compare concrete observable approaches while leaving legal caution judgment unresolved.
- Check yellow lens and official conjunction; do not apply flashing-red branch from another subsection.

## Current checkpoint

Four planned cases compare a heavy vehicle from east/west approaches, engineering approach speed and crossing-traffic presence while retaining the same official flashing-yellow premise. `flashing_yellow_heavy.py` requests a physical yellow signal head, linked official device, blind intersection, heavy subject and optional crossing vehicle through an adapter. Its source-shaped measurement requires original 20 Hz signal and participant readbacks and keeps the legal “with caution” judgment open. Tests cover both approach directions, creation calls, missing-source rejection and fixed-condition comparison; `cpu-tests.log` SHA256 is `af7e3f206e5267a8ff2e06d0a2fefd00e69a646799c2c61bbcd2fecaea8941d3`.

Status remains partial. A concrete Native adapter, four-camera capture, exact runner/config/construction, three fallbacks per case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C24753__NRS-484B-310-2__heavy_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C24753__NRS-484B-310-2__heavy_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C24753__NRS-484B-310-2__heavy_vehicle_driver --complete`. Strict readiness still fails while this package is partial.

## 2026-11-17 concrete Native signal and heavy-vehicle adapter checkpoint

Restored `flashing_yellow_heavy.py` and its test file from the exact-byte archives already retained in `result.json`. The source now contains CARLA-lazy `discover_native_control`, `construct_native`, and `NativeYellowController`. The helper selects separate east/west signal heads with OpenDRIVE IDs and affected-lane waypoints at one junction, derives the governed heavy route and a perpendicular crossing route from original map waypoints, spawns explicitly chosen heavy and crossing blueprints, destroys an owned actor on failed construction, commands and reads back the yellow/off signal state per tick, and verifies restoration of its initial state. Official status remains a cited premise, not inferred from the simulated traffic light. No CARLA run or legal caution judgment is claimed.

The returned fake-world test exercises both directions, all four planned cases, heavy/crossing actor creation, missing official-control premise, failed crossing spawn cleanup, yellow/off readback and light restoration. Four package tests pass in `cpu-tests.log` SHA-256 `49562b4da647cd8f2933d1d524589c471e7ff7f8126065f2e04e1d199a4a7bbf`; current source SHA-256 `8b34ca8e548fb2a0cbf7934e2e777e4049495e51f5397b0e751c889050bdd68e`. Pinned CPU preflight and scoped nonstrict `worker_check.py --complete` pass. Scoped strict still exits 1 at `preparation.py:276` because this result remains partial.

Next worker CPU action: build one exact selected case around this Native helper with the four named raw camera streams, frame-joined signal/device/vehicle source readback, finalizer and source-bound positive/missing-source compatibility; then run `process-saved` before expanding the other selected cases and three fallbacks each. Independent comparisons, physical preparation, semantic proposal and delivery audit remain to construct.

To remain within the 10,200-file return cap, exact bytes of three no-longer-live helper scripts were added to `work/_shared/historical-receipts-bundle-20261116.json` and their owner scoped strict gates passed after removal: C111706 `validate_semantic.py`, C230627 `validate_semantic.py`, and C102304 `validate_delivery_bindings.py`. Two other trial removals failed their owner scoped strict gate and were restored byte-identically before this checkpoint. The returned tree is 10,200 files with none above 2 MiB. No frozen input, runtime, batch, or Git operation changed.
