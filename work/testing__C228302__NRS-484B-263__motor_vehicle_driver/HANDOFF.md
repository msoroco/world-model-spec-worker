# testing__C228302__NRS-484B-263__motor_vehicle_driver

Status: partial. Exact static check passed; strict delivery readiness failed because this package remains partial. No accepted recording exists for this assignment, and no legal judgment has been made.

## Source and branch review

- NRS 484B.263 requires an exiting driver to yield to **all** approaching highway vehicles whose proximity constitutes an immediate hazard, and to continue yielding until reasonable safety. The assigned C228302 branch is exit only; the entering alternative is outside its fixed maneuver.
- A controlled-access highway requires sourced public dedication/access and an authority restriction determination. Map appearance alone is insufficient. `controlled_access_exit.py:validate_site` requires these sources and runtime map/connection readback.
- `case-plan.json` records zero accepted evidence, three source gaps, all five exact cases and four comparisons. No statutory numeric boundary or judgment training range is supplied; headway values are physical probes, not legal cutoffs.

## Implemented CPU work

- `controlled_access_exit.py` implements source-gated construction with a real exit route, one or two approaching highway vehicles, policy controller requests, cleanup on failure, 900 original-frame 20 Hz measurement, all-actor identity checks and comparison isolation. Controller requests and measured conduct remain distinct.
- `finalize_saved.py` remeasures saved original rows and rejects stale hashes or altered measurements. `saved_audit.py` independently rejects missing sealed Native sources, truncated or misaligned original frames, missing four-camera full decodes and pixels, stale measurement sources, absent exit entry or unsupported legal labels.
- `tests/` has 16 passing tests, including positive and negative source, construction, original-frame and audit paths. `cpu-tests.log` SHA256 `8daaed445b06b045d9a1393f4690e434f1e38f992fb4914f3480a2e027598d10`.
- Exact `.venv-cpu/bin/python worker_check.py --assignment testing__C228302__NRS-484B-263__motor_vehicle_driver --complete` passed; see `static-check.log` SHA256 `1b55098fd9792e7794c1a54b42a3a5a73b192bc2679ad51cdc098e60d14ac6eb`. Exact strict command with `--require-delivery-ready` failed at partial-package acceptance; see `strict-check.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

## Next CPU actions

1. Bind original map authority/dedication/access sources and map exit geometry into executable per-case config, construction hashes and 20 Hz four-camera capture; implement a controller that requests each policy without substituting teleports or labels.
2. Write canonical semantic proposals and `semantic-index.json`; add selected-requirement measurement contracts and exact execution manifest entries. Assess physical risk per case and add tested fallback construction only where a concrete trigger supports one.
3. Produce source-hashed case-specific diagnostics, exact offline and positive/negative compatibility proofs for every case/candidate, saved-only `process-saved` receipts and delivery audit positive/negative receipts. Test feedback and independent comparison audits on sealed original packets.
4. Rerun focused tests and both exact check commands, then update `result.json`. Keep status partial until the strict check passes.

Pinned preflight `.venv-cpu/bin/python runtime.py preflight` passed this turn. Do not claim physical verification from synthetic packets.
