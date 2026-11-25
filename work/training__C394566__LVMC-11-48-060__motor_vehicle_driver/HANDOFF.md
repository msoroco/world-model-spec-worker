# training__C394566__LVMC-11-48-060__motor_vehicle_driver

Status: **partial**, current-runtime CPU construction and source diagnostics pass. Exact scoped strict readiness has not passed.

## Exact law and coverage

LVMC 11.48.060 bars use of a non-truck street as a through route from one truck route to another unless pickup, delivery or essential use is required enroute. The frozen C394566 motor-vehicle actor is surveyed as a truck. Full-train has no accepted recordings for this requirement. The two selected exact cases share road topology, truck class, camera policy, 30 seconds at 20 Hz and route geometry: `probe_01` has no reviewed enroute purpose; `probe_02` has an independently reviewed service premise and pickup, delivery or essential purpose plus a 100-frame service stop on the intervening road. Stop duration is an engineering observation, not a legal threshold or proof of purpose.

## Executable Native construction

The two selected cases and their faster-cruise `fallback1` candidates have inline bundles under `native/`. `native/selected-offline-manifest.json` binds each exact case and construction. Four-view source camera names now match the current runtime profile (`overview`, `approach`, `reference_corner`, `driver_reference`). The primary and fallback for each case pass `runtime.py offline`; unittest discovery ran 2 tests for `probe_01` and 3 for `probe_02` per candidate. The fallback trigger is failure of original source trace to reach the exit truck route within 600 frames, and its knobs are only speed target and throttle cap. These checks never start CARLA.

- `probe_01` `primary`: `selected-primary-construction.json` SHA-256 `886834532d2d9f3e83818e79b64e2f145713b7800500015e4da21414178b684b`; `selected-primary-offline.log` SHA-256 `18b93cd3bd407fb07add22b3d4acac11ea486b1883d3d54f3131a3d22b4e275d`; exit 0.
- `probe_01` `fallback1`: `selected-primary-fallback1-construction.json` SHA-256 `50cff753b6d5c072a58e35d1b8469f0256acf1106ddbdd07984bbb1657b00da4`; `selected-primary-fallback1-offline.log` SHA-256 `18b93cd3bd407fb07add22b3d4acac11ea486b1883d3d54f3131a3d22b4e275d`; exit 0.
- `probe_02` `primary`: `selected-purpose-construction.json` SHA-256 `14574e81fb27fbae54d0818768d40ba73e8f1818528d3fc4c2a4a0d184c287a6`; `selected-purpose-offline.log` SHA-256 `62f2be104a6f3925639a4d920053414d3950e6a2ad2a983af2a5be020b73ea24`; exit 0.
- `probe_02` `fallback1`: `selected-purpose-fallback1-construction.json` SHA-256 `130e0cd80129a981a4e7e76a113de0fcf1713ed6195876907b6804bddfb993f7`; `selected-purpose-fallback1-offline.log` SHA-256 `62f2be104a6f3925639a4d920053414d3950e6a2ad2a983af2a5be020b73ea24`; exit 0.

## Independent source checks

`native/measure_through_route.py` joins 600 original Native route rows, frame map and four decoded camera sources; requires independently reviewed truck-route designations, truck blueprint/class, connectivity, purpose and premises source. It rejects missing source/identity/hash and measures a complete three-road passage. `native/measure_purpose_route.py` also requires an original 100-frame service stop on the intervening street and reviewed non-none purpose. Neither script issues a legal verdict.

`native/prove_through_route.py` passes four route/purpose variants and rejects source, frame, actor, geometry, designation and purpose mutations. `native/comparison_audit.py` rereads both original source directories and checks shared route/designation/truck context, complete passages, spatial route/length tolerance, exact case identity and reviewed purpose difference. `native/prove_comparison.py` passes synthetic comparison and five negatives (wrong purpose, changed route source, changed truck class, incomplete and interrupted stop).

- Source proof log: `native/through-route-proof.log`, SHA-256 `059a50a0947dca56c0c8c80e90da414344881b1a3e7693d2837fa533640ae1e8`.
- Comparison proof log: `native/comparison-proof.log`, SHA-256 `57a0cea36d511b0805df0188855d69b21b1cab6ffd7719e0b40d21e34416aad4`.

## Remaining CPU work

Build the full current-runtime execution manifest, source-hashed fixture recipes, exact measurement contracts and Core finalizers for both cases and fallbacks. Run positive/negative `runtime.py compatibility` and recorded-only `runtime.py process-saved` receipts. Author the six semantic stage proposals and independent delivery acceptance audit; bind the comparison audit to the exact saved receipts. Add root canonical runner/config/construction/camera plan and then run `.venv-cpu/bin/python worker_check.py --assignment training__C394566__LVMC-11-48-060__motor_vehicle_driver --complete --require-delivery-ready`. Result remains partial until that command succeeds.

## Local physical review

The operator must survey a real connected two-truck-route journey over an intervening non-truck street, verify a truck blueprint and service premise, then independently inspect original route IDs, actor, purpose sources, camera pixels and physical completion. No CARLA run, original recording, canonical acceptance or legal verdict is claimed.
