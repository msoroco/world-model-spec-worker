# training__C394566__LVMC-11-48-060__motor_vehicle_driver

Status: **partial**. Exact `probe_01` is selected for a truck-route-to-truck-route through trip over an intervening non-truck street, with no enroute purpose claimed. Its survey-gated Native primary passes pinned offline and source-shaped route/purpose diagnostics pass. Full CPU delivery proofs remain open.

Exact LVMC 11.48.060 addresses non-truck streets used as through routes between two truck routes unless pickup, delivery or essential use is required enroute. The frozen witness asks for a complete passage. Full-train accepted membership is empty. The frozen actor is `motor_vehicle_driver`; the Native survey requires a truck blueprint and source review of truck identity. A stationary interval alone never proves a pickup, delivery or essential purpose.

## Implemented checkpoint

- `native/selected_primary/runner.py` checks exact identity without CARLA and requires a reviewed map, truck blueprint, two designated truck-route road IDs, intervening non-truck road ID and route waypoints. It uses waypoint steering with throttle/brake feedback, records 600 original frame IDs at 20 Hz, original road IDs/pose/speed/vehicle identity and four vehicle-mounted source camera videos. The source trace must actually complete the three-road passage; a requested route does not prove it.
- `native/measure_through_route.py` joins all 600 raw Native rows, original frame map, four decoded cameras and independently reviewed route/purpose context. Original cameras require capture-profile resolutions and byte hashes. It measures road sequence, route length and stationary frames, and reports reviewed enroute purpose separately without a legal verdict.
- `native/prove_through_route.py` passed four synthetic variants: complete passage with no purpose, complete passage with delivery purpose, incomplete trip and direct truck-route transition. It rejected eight frame, provenance, actor, route-jump, camera-hash, designation-source, purpose and route-ID mutations. Log: `native/through-route-proof.log`, SHA-256 `700ab53639f91315ea3bdfcabe7365faddd90e501271fc989d308553dcf12ede`. This is software proof only.
- Exact inline Native bundle: `native/selected-primary-construction.json`, SHA-256 `235b85071124e0b6867601bca045c86f5cae83ffcda791820fd61885e705b66d`. Pinned `runtime.py offline` exited 0: `native/selected-primary-offline.log`, SHA-256 `4c2b07da4a0359bef7a15e3ca6ad50ed3689f15dd429affe401c2f3735e3cbfb`.

## Commands and next CPU work

Executed with `PYTHONDONTWRITEBYTECODE=1` and `TMPDIR=$PWD/.runtime-work/c394566-test`:

```text
.venv-cpu/bin/python work/training__C394566__LVMC-11-48-060__motor_vehicle_driver/native/prove_through_route.py
.venv-cpu/bin/python work/training__C394566__LVMC-11-48-060__motor_vehicle_driver/native/build_selected.py
.venv-cpu/bin/python runtime.py offline --manifest work/training__C394566__LVMC-11-48-060__motor_vehicle_driver/native/selected-offline-manifest.json --case training__C394566__LVMC-11-48-060__motor_vehicle_driver__probe_01 --output .runtime-work/c394566-selected-primary-offline
```

Next: build full pinned compatibility and saved-processing manifest/fixtures, Core mapping, finalizer, semantic proposals and independent audits. Construct exact `probe_02` with documented enroute pickup/delivery/essential purpose and controlled comparison on the same route. Physically verify the route topology, truck vehicle, original road IDs, pixels and purpose evidence locally. No original capture, physical acceptance or legal verdict is claimed.
