# training__C150916__NRS-484B-220-1__motor_vehicle_driver

Status: ready for local Native delivery preparation. The assignment-scoped strict CPU gate passed on 2026-11-25. No original Native capture, accepted recording, physical sign pixel, official sign authority, or legal verdict is claimed.

## Selected exact cases

- `training__C150916__NRS-484B-220-1__motor_vehicle_driver__designated`: requested travel in the designated one-way direction.
- `training__C150916__NRS-484B-220-1__motor_vehicle_driver__opposite`: requested travel opposed to the designated one-way direction.
- `training__C150916__NRS-484B-220-1__motor_vehicle_driver__comparison`: same authored road, sign requests, source context, camera profile and frame map; only requested and measured travel direction differs.

Each case has a 600-frame, 20 Hz, 30-second four-camera Native construction, a primary 8 m/s candidate, a fallback 5 m/s candidate, and a source-bound measurement contract. The manifest SHA-256 is `d4ea2e57ca083b71106e0c1ffded94bd82180ca4cb54627496131adf4b4099b5`. The final case-plan and fixture-recipe bytes were frozen before the four v6 compatibility proofs.

## CPU proofs

The four exact primary/fallback offline and current-runtime compatibility tests passed, including positive analysis and missing-source negative checks. Both recorded-only `runtime.py process-saved` runs preserved original source hashes, joined 600 original frames, and decoded the final video. Both independent delivery audits passed and rejected missing original pose. Source-shaped physical complete/incomplete/missing diagnostics and the lifecycle-order negative passed. The five-stage canonical semantic chain validated two selected cases. The comparison audit passed and rejected an unchanged-direction negative. The native unit suite passed 2 tests. The exact scoped strict command passed: `.venv-cpu/bin/python worker_check.py --assignment training__C150916__NRS-484B-220-1__motor_vehicle_driver --complete --require-delivery-ready`.

These proofs use synthetic diagnostic fixtures for software preparation. Local delivery must execute the Native CARLA run, inspect all four actual camera views and sign pixels, review one-way designation and official sign authority from original sources, measure realized vehicle direction, and perform physical and legal acceptance. Membership rows are not treated as accepted source evidence.

## Legacy source context

The older eight 240-frame request bundles remain retained as source-bound preliminary checks. They do not substitute for the selected 600-frame current-runtime cases. Exact frozen assignment SHA-256: `67e058bbd9f823806f1eedfb21be7c56be27d3128b71bac2772a5f3b83da919f`.
