# C394566 / LVMC 11.48.060 motor vehicle driver

Status: **ready / delivery_prepared**. Exact scoped strict gate passed on 2026-11-24 with exit 0; `scoped-strict-check.log` reports `static_checks_passed: true` for this assignment. This is a CPU delivery package, awaiting an actual CARLA GPU capture and independent review.

## Exact selected cases

`probe_01` models a truck traversing a connected non-truck street between two truck routes without a reviewed enroute purpose. `probe_02` holds route, truck, duration, capture policy and approximately 84 m of spatial progress fixed, but supplies independently reviewed pickup, delivery or essential-purpose context and a 100-frame service stop. The stop is an observation, not proof of lawful purpose or a statutory threshold. Both cases have `primary` and `fallback1` Native constructions; fallback changes only speed target and throttle cap if the original source trace fails to reach the exit truck route within 600 frames.

## CPU evidence

All four case/candidate Native offline checks pass. Four current-runtime compatibility receipts under `compat-p01-pr/`, `compat-p01-fb/`, `compat-p02-pr/` and `compat-p02-fb/` pass Native validation, converter, Lean decoder, render/full decode and selected measurements. Both primary saved-only receipts, `saved-p01-processing.json` and `saved-p02-processing.json`, pass with 600 original frame joins and preserved original source hashes. `native/prove_physical.py` passes source-shaped complete, incomplete and missing-source outcomes for each case and lifecycle ordering; those fixtures are synthetic. The independent source, comparison and finalizer proofs are under `native/`.

Six source-hashed semantic stages are under `proposals/`, with `semantic-index.json`. The qualitative phrase “essential use is required enroute” remains an unresolved judgment; no numeric legal threshold was invented. Positive and missing-source negative delivery audits pass for each selected case, and positive and fixed-route-drift negative comparison audits pass. The current-runtime branch, execution manifest, semantic, delivery and four-receipt compatibility validators passed in `pre-ready-validation.log`. The canonical root runner/config/construction and four-view camera plan are present. `runtime-preflight.log` confirms pinned CPU dependencies and FFmpeg, Lean and Lake availability.

The exact scoped command `.venv-cpu/bin/python worker_check.py --assignment training__C394566__LVMC-11-48-060__motor_vehicle_driver --complete --require-delivery-ready` passed after the source-observation mapping and recorded context channels were made explicit. The output is `scoped-strict-check.log`.

## Remaining GPU review

Execute the selected delivery case through the canonical command in `result.json`, survey an actual connected truck-route journey, verify the real truck class and served premises, and inspect original route IDs, camera pixels, physical completion and purpose sources. Synthetic compatibility and saved-only receipts do not establish a real capture or a legal verdict.
