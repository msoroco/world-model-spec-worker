# C394554 transit-stop supplemental branch

C394554 is the unallocated motorist-compatible `road/travel/bus_stop` cell for frozen NRS 484B.280(1)(c). The two exact cases are `waiting_at_stop` and `boarding_bus`; the controlled comparison is `transit_passenger_state`. The original ready C233871 package was preserved. The case difference is passenger motion toward a bus-side proxy; the law sets no numeric distance or braking cutoff.

Construction uses source-hashed original OpenDRIVE, physical stop-prop and public bus readback, pedestrian and driver input history, synchronized frame joins, and four-view capture. Asset absence is source-gated. The bus-body proxy does not establish an actual door. Native pixels must independently show the stop, bus, actual door and pedestrian ingress before production delivery audit can pass; fixture-only pixel review is explicitly rejected by the production audit. Human observation and legal proper caution remain unresolved.

## CPU proof receipts

- 13 focused CPU tests passed in `cpu-tests.log`; canonical semantic stages passed in `semantic-stage-check.log`.
- Both exact case primary constructions and paired same-road upstream ego-spawn fallbacks passed refreshed offline and full positive/negative compatibility proofs. The four `proof-*.log` and `compat-*-receipt.json` files are bound by `execution-manifest.json` to construction hashes.
- `waiting_at_stop`: primary/fallback offline and compatibility passed; saved-only processing passed; physical/lifecycle fixture `physical-waiting_at_stop-proof.json`; audit positive and tampered-original negative logs `audit-waiting_at_stop-positive.log` / `audit-waiting_at_stop-negative.log`. Original Native stop, bus door and pixels remain unreviewed.
- `boarding_bus`: primary/fallback offline and compatibility passed; saved-only processing passed; physical/lifecycle fixture `physical-boarding_bus-proof.json`; audit positive and tampered-original negative logs `audit-boarding_bus-positive.log` / `audit-boarding_bus-negative.log`. Original Native stop, bus door and pixels remain unreviewed.
- Controlled comparison fixture `comparison-fixture-proof.json` passes with measured approach 0.0 m versus 0.5 m, while `actual_boarding_reviewed` is false and `legal_verdict` is null.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C394554__NRS-484B-280-1c__motor_vehicle_driver --complete` passed. The exact `--complete --require-delivery-ready` CLI was run and rejects truthful partial status.

## Exact strict gate diagnostic

The result remains `partial`. With an in-memory ready-status diagnostic and no file change, the frozen `portable.validate_imports` reads `inputs/testing__C394554__NRS-484B-280-1c__motor_vehicle_driver/assignment.json` and raises `FileNotFoundError`; this supplemental binding exists at `work/.../assignment.json` as required by the branch workflow. An in-memory read-path override only for that missing supplemental input let the entire assignment-scoped strict check pass. This does not make the frozen CLI pass and is not a ready claim. No frozen input, runtime or shared file was changed.

`queue-proposal.json` is local for lead review and has not been published. Native physical capture, actual pixel review, independent local acceptance and legal judgments remain pending. All temporary files are under `.runtime-work/c394554/`; returned files are UTF-8 and at most 2 MiB, with no trailing whitespace or blank EOF.

## 2026-11-27 current-runtime independent review

- Reran 13 focused tests (`cpu-tests-nov27.log`, exit 0) and scoped `--complete` (`scoped-complete-nov27.log`, exit 0). Reran exact scoped strict CLI (`scoped-strict-nov27.log`, exit 1); it rejects the truthful partial status at `preparation.py:267`. No ready status is asserted.
- Read the original NRS 484B.280(1)(c) text, supplemental binding, source-hashed Native site/encounter code, saved measurement, independent delivery audit, controlled comparison, and existing case proofs. The bus body upper-side region is an engineering proxy. The production audit requires a reviewer bound to original video and frame-map hashes to confirm an actual door and pedestrian ingress; the CPU fixture remains explicitly insufficient.
- Existing in-memory ready-path diagnostic reaches `portable.validate_imports`, which reads a missing frozen `inputs/<supplemental-id>/assignment.json`. The exact supplemental assignment is correctly returned at `work/<supplemental-id>/assignment.json` under FULL_BRANCH_CONTRACT. This runtime path mismatch remains the exact strict-gate failure after a status change, so retain `partial` without altering frozen inputs or runtime.

## 2026-11-27 Native lifecycle and lane-placement repair

- Repaired `native_capture.py` to start the original CARLA recorder before capture, stop it before acquisition hashing, and require a nonempty original recorder file. Cleanup stops an active recorder after errors. The prior runner hashed an uncreated `carla_recorder.log`.
- The approach and reference-corner cameras now compute yaw and pitch toward the read-back bus and stop positions. The old reference-corner yaw pointed away from the transit encounter. The ego now spawns at the source driving-lane waypoint center and heading; route readback checks same road/lane, forward direction, and an engineering projection tolerance. This avoids a centerline spawn when the authored y=0 coordinate projects to a lane at y=1.75 m.
- `cpu-tests-deep-nov27.log`: 16 focused CPU tests pass, including recorder start/stop, source lane projection/direction, and actual camera aim. Refreshed both case primary and paired fallback constructions. All four `proof-*.log` offline checks and `compat-*-receipt.json` positive/negative compatibility checks pass against the new construction SHA256 values. Refreshed synthetic motion/lifecycle receipts and recorded-only `saved-*.log` proofs for both exact cases. These remain software fixtures, not original CARLA pixels.
- `scoped-complete-deep-nov27.log`: assignment `--complete` passes. `scoped-strict-deep-nov27.log`: exact assignment strict CLI exits 1 at the truthful partial-status check. The supplemental-input lookup described above has not changed; retain partial status. Original physical door/ingress pixels and legal proper-caution review remain for local evaluation.
- The authored ego approach now uses y=1.75 m for both exact cases; the Native lane query uses that coordinate and then spawns at the original waypoint center with source yaw. This removes the road-centerline tie between opposing lanes. The 16 focused tests, all four offline/compatibility checks, and both saved-only runs were repeated after this change.
