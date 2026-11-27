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
