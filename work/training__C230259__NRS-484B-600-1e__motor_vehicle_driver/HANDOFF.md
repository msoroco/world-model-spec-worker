# training__C230259__NRS-484B-600-1e__motor_vehicle_driver

Status: **partial**. Exact `probe_03` is selected for a requested above-cap speed attempt. Its survey-gated Native primary passes pinned offline; source-shaped velocity diagnostics pass. Full CPU delivery proofs remain open.

Exact NRS 484B.600(1)(e) states a rate greater than 80 mph is unlawful in any event for a vehicle of any kind or character. No posted speed sign is a prerequisite. Both frozen witness rows have empty accepted membership in their target sets. Requested controller speed is never treated as measured velocity. The selected case is an 85 mph requested-speed attempt, subject to actual Native speed and route review.

## Implemented checkpoint

- `native/selected_primary/runner.py` checks exact identity without CARLA and requires a reviewed map, vehicle capability and clear route survey before capture. It applies throttle/brake feedback toward a requested 85 mph, records 600 original frame IDs at 20 Hz, actual three-component Native velocity and actor identity, and four source camera streams. It rejects a changed road or reversed travel. Original speed is not claimed by this CPU check.
- `native/measure_absolute_speed.py` joins all 600 original frame IDs, raw velocity samples, vehicle/driving-state source review and four decoded camera files. Original cameras must match the capture profile and camera byte hashes. It reports measured maximum and frames greater than 80 mph while driving, without a posted-sign dependency or legal verdict.
- `native/prove_absolute_speed.py` passed synthetic 75, 79.5, 80 and 85 mph variants, with zero above-cap frames for the first three and 600 for 85. It rejected seven frame, provenance, actor, nonfinite velocity, driving-state, camera-hash and route-source mutations. Log: `native/absolute-speed-proof.log`, SHA-256 `dcafd640bad2f83f53213ec47c610990b347de1cd16ff646de34332fe5f65512`. This is software proof only.
- Exact inline Native bundle: `native/selected-primary-construction.json`, SHA-256 `119e43a35cedc57a27f596df00b3d2f1011ace515611efe413743512650c1267`. Pinned `runtime.py offline` exited 0: `native/selected-primary-offline.log`, SHA-256 `88a3a35dc095b0cb134817577fac9b089bc5b96694b4a3034855231853a978b1`.

## Commands and next CPU work

Executed with `PYTHONDONTWRITEBYTECODE=1` and `TMPDIR=$PWD/.runtime-work/c230259-test`:

```text
.venv-cpu/bin/python work/training__C230259__NRS-484B-600-1e__motor_vehicle_driver/native/prove_absolute_speed.py
.venv-cpu/bin/python work/training__C230259__NRS-484B-600-1e__motor_vehicle_driver/native/build_selected.py
.venv-cpu/bin/python runtime.py offline --manifest work/training__C230259__NRS-484B-600-1e__motor_vehicle_driver/native/selected-offline-manifest.json --case training__C230259__NRS-484B-600-1e__motor_vehicle_driver__probe_03 --output .runtime-work/c230259-selected-primary-offline
```

Next: build the full pinned compatibility and saved-processing manifest/fixtures from raw trace and cameras, Core mapping, finalizer, semantic proposals and independent audits. Construct distinct `probe_01` and `probe_02` below-cap attempts on the same reviewed route and test a controlled measured-speed comparison. Physical route suitability, actual achieved speed, camera pixels and original source review require a local Native run. No physical acceptance or legal verdict is claimed.
