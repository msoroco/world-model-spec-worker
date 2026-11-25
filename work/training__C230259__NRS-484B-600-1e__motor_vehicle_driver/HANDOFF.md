# training__C230259__NRS-484B-600-1e__motor_vehicle_driver

Status: **partial**. Exact `probe_01`, `probe_02` and `probe_03` are selected as requested 75, 80 and 85 mph attempts. Their standard four-camera Native corridor constructions pass pinned offline; each constructs a separate other vehicle in the second same-direction lane. These requests do not establish measured below/at/above observations. Full CPU delivery proofs remain open.

Exact NRS 484B.600(1)(e) states a rate greater than 80 mph is unlawful in any event for a vehicle of any kind or character. No posted speed sign is a prerequisite. Both frozen witness rows have empty accepted membership in their target sets. Requested controller speed is never treated as measured velocity. The selected case is an 85 mph requested-speed attempt, subject to actual Native speed and route review.

## Implemented checkpoint

- `native/selected_primary/runner.py` checks exact identity without CARLA and requires a reviewed map, vehicle capability and clear route survey before capture. It applies throttle/brake feedback toward a requested 85 mph, records 600 original frame IDs at 20 Hz, actual three-component Native velocity and actor identity, and four source camera streams. It rejects a changed road or reversed travel. Original speed is not claimed by this CPU check.
- `native/measure_absolute_speed.py` joins all 600 original frame IDs, raw velocity samples, vehicle/driving-state source review and four decoded camera files. Original cameras must match the capture profile and camera byte hashes. It reports measured maximum and frames greater than 80 mph while driving, without a posted-sign dependency or legal verdict.
- `native/prove_absolute_speed.py` passed synthetic 75, 79.5, 80 and 85 mph variants, with zero above-cap frames for the first three and 600 for 85. It rejected seven frame, provenance, actor, nonfinite velocity, driving-state, camera-hash and route-source mutations. Log: `native/absolute-speed-proof.log`, SHA-256 `dcafd640bad2f83f53213ec47c610990b347de1cd16ff646de34332fe5f65512`. This is software proof only.
- Three inline Native bundles are listed in `native/selected-offline-manifest.json`: `probe_01` construction SHA-256 `5836a0a13f2ccb577d8f8f37ff0b313a5b66713cc5fb2425e9d3a11f77117d72`, `probe_02` `0a1f3f29400437e0d27f0ff561018ea9474e025d1068b91702c89ab655f6cbc0`, and `probe_03` `46a2300af9d0cb80e9752a080e58203eba8d8247328164481ef7687cac8e7e11`. Their exact `runtime.py offline` logs are `native/probe_01-offline.log` SHA-256 `7fb71dfaa99beb6503df9d5894b211d4e9e6be4ae35efdb0be6c39a4b72e2b75`, `native/probe_02-offline.log` `34c46173d47ef741a00c2482041290408781f8f17ae50356ba5f8ab1f083682b`, and `native/probe_03-offline.log` `e2d0e6f7b0a26ff00412af049c34454ba270b638fa226a0cc696c108b714de9c`.
- `native/comparison_audit.py` checks three original saved-source observations, their context hashes, fixed route/vehicle/driving sources, and measured below/at/above 80 mph values. Five CPU positive/negative tests pass in `native/comparison-audit-tests.log`, SHA-256 `246efeefe8ca7af6327050bbf8bcf37df137928a324e9d11c788d1f363ca646e`. These are synthetic schema tests, not a measured physical comparison.

## Commands and next CPU work

Executed with `PYTHONDONTWRITEBYTECODE=1` and `TMPDIR=$PWD/.runtime-work/c230259-test`:

```text
.venv-cpu/bin/python work/training__C230259__NRS-484B-600-1e__motor_vehicle_driver/native/prove_absolute_speed.py
.venv-cpu/bin/python work/training__C230259__NRS-484B-600-1e__motor_vehicle_driver/native/build_selected.py
.venv-cpu/bin/python runtime.py offline --manifest work/training__C230259__NRS-484B-600-1e__motor_vehicle_driver/native/selected-offline-manifest.json --case training__C230259__NRS-484B-600-1e__motor_vehicle_driver__probe_01 --output .runtime-work/c230259-owner/offline-01
.venv-cpu/bin/python runtime.py offline --manifest work/training__C230259__NRS-484B-600-1e__motor_vehicle_driver/native/selected-offline-manifest.json --case training__C230259__NRS-484B-600-1e__motor_vehicle_driver__probe_02 --output .runtime-work/c230259-owner/offline-02
.venv-cpu/bin/python runtime.py offline --manifest work/training__C230259__NRS-484B-600-1e__motor_vehicle_driver/native/selected-offline-manifest.json --case training__C230259__NRS-484B-600-1e__motor_vehicle_driver__probe_03 --output .runtime-work/c230259-owner/offline-03
.venv-cpu/bin/python -m unittest discover -s work/training__C230259__NRS-484B-600-1e__motor_vehicle_driver/native -p test_comparison_audit.py -v
```

Next CPU work: adapt the current Native bundles to the pinned four-view capture profile and finalization protocol, with exact source packets and Core mapping. Build three full execution-manifest entries, measurement contracts, positive/negative compatibility recipes and saved-only processing receipts. Add canonical semantic proposals, independent delivery audit and its negative test, then bind the tested comparison audit to saved observations. The Native bundle now uses the pinned four-camera names and dimensions, but canonical capture/finalization and saved-only processing remain unproven. Physical route suitability, actual achieved speed, camera pixels and original source review require a local Native run. No physical acceptance or legal verdict is claimed.
