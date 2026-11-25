# training__C230259__NRS-484B-600-1e__motor_vehicle_driver

Status: **partial**. Exact `probe_01`, `probe_02` and `probe_03` are selected as requested 75, 80 and 85 mph attempts. Their survey-gated Native primaries pass pinned offline. These requests do not establish measured below/at/above observations. Full CPU delivery proofs remain open.

Exact NRS 484B.600(1)(e) states a rate greater than 80 mph is unlawful in any event for a vehicle of any kind or character. No posted speed sign is a prerequisite. Both frozen witness rows have empty accepted membership in their target sets. Requested controller speed is never treated as measured velocity. The selected case is an 85 mph requested-speed attempt, subject to actual Native speed and route review.

## Implemented checkpoint

- `native/selected_primary/runner.py` checks exact identity without CARLA and requires a reviewed map, vehicle capability and clear route survey before capture. It applies throttle/brake feedback toward a requested 85 mph, records 600 original frame IDs at 20 Hz, actual three-component Native velocity and actor identity, and four source camera streams. It rejects a changed road or reversed travel. Original speed is not claimed by this CPU check.
- `native/measure_absolute_speed.py` joins all 600 original frame IDs, raw velocity samples, vehicle/driving-state source review and four decoded camera files. Original cameras must match the capture profile and camera byte hashes. It reports measured maximum and frames greater than 80 mph while driving, without a posted-sign dependency or legal verdict.
- `native/prove_absolute_speed.py` passed synthetic 75, 79.5, 80 and 85 mph variants, with zero above-cap frames for the first three and 600 for 85. It rejected seven frame, provenance, actor, nonfinite velocity, driving-state, camera-hash and route-source mutations. Log: `native/absolute-speed-proof.log`, SHA-256 `dcafd640bad2f83f53213ec47c610990b347de1cd16ff646de34332fe5f65512`. This is software proof only.
- Three inline Native bundles are listed in `native/selected-offline-manifest.json`: `probe_01` construction SHA-256 `8240f52ddb5bb76f3b0fe8b107f7ed9a3df8e324bdb057f7bd78f9ad56b5d690`, `probe_02` `381d2405c8ee45910cee0f67d363502408d6c7949a8d6982d6187b7364c01077`, and `probe_03` `2a71d61b64634f624625eb76e8d7f761201049a4107a544e7261087983c20ee0`. Their exact `runtime.py offline` logs are `native/probe_01-offline.log` SHA-256 `ef3ea8668305a2dd697e4cc4dab67f432a9da88de1be74f4cc50fd9293323863`, `native/probe_02-offline.log` `11bf55c0a5ca7e6983092cc0417fc076a09faadc8a3bcbd28bc6cbf1f31053ff`, and `native/probe_03-offline.log` `21a24ae17812eaecfb7ba8d734f6d049ebb9be8c6e0d9fa5bd372a29ae7775fe`.
- `native/comparison_audit.py` checks three original saved-source observations, their context hashes, fixed route/vehicle/driving sources, and measured below/at/above 80 mph values. Five CPU positive/negative tests pass in `native/comparison-audit-tests.log`, SHA-256 `0cdb708e7bac016572af66ea7a35a87891f9530f1aa5b9b49a9f70a6090f6531`. These are synthetic schema tests, not a measured physical comparison.

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

Next CPU work: adapt the current Native bundles to the pinned four-view capture profile and finalization protocol, with exact source packets and Core mapping. Build three full execution-manifest entries, measurement contracts, positive/negative compatibility recipes and saved-only processing receipts. Add canonical semantic proposals, independent delivery audit and its negative test, then bind the tested comparison audit to saved observations. The current bundle's camera names and direct video source format do not yet satisfy the full runtime delivery profile. Physical route suitability, actual achieved speed, camera pixels and original source review require a local Native run. No physical acceptance or legal verdict is claimed.
