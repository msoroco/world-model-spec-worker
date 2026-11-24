# training__C262666__NRS-484B-363-1__heavy_vehicle_driver

Status: **partial**. Exact `probe_03` is selected for an active school-zone above-15 mph attempt with a heavy motor vehicle. Its survey-gated Native primary passes pinned offline and a source-shaped speed/exception diagnostic passes. Full CPU delivery proofs remain open.

Exact NRS 484B.363(1), including the beacon definition in (9), requires a designated school zone and sets 15 mph subject to four exceptions: no school session day; the half-hour interval after school ceases until a half hour before it resumes; an operational beacon not flashing during class hours; or, without such a beacon, a sign indicating the limit is off. The witness calls for a heavy vehicle crossing the scene; the full-train accepted membership is empty. Crosswalk pixels cannot establish calendar, legal designation, or beacon/sign authority.

## Implemented checkpoint

- `native/selected_primary/runner.py` checks exact identity without CARLA and requires a reviewed map/route, heavy vehicle, zone designation, sign, calendar, civil time and beacon sources. It requests 17 mph, records 600 original frame IDs at 20 Hz, Native road/position/velocity/ego identity and four source camera videos. Requested speed is never treated as observed speed. Its context template leaves school-day, beacon and designation facts for independent review.
- `native/measure_school_zone.py` joins all 600 raw Native rows, original frame map, four decoded camera files and reviewed zone context. It requires camera byte hashes and capture-profile resolutions, timezone-aware civil time, stable condition review, designation, school calendar/schedule, operational beacon or nonbeacon sign state, motor vehicle identity and zone bounds. It reports observed zone speed and each exception fact separately without a legal verdict.
- `native/prove_school_zone.py` passed seven synthetic variants: active below/above 15 mph, no school day, half-hour exception, class-hours nonflashing beacon, nonbeacon sign off and nonbeacon sign on. It rejected eight frame, provenance, road, velocity, camera-hash, calendar-source, civil-time and beacon-fact mutations. Log: `native/school-zone-proof.log`, SHA-256 `84b0fe806b1bc872561e0bf5ca3a059a0cebffd2519a7246ed5da7a036afe46e`. This is software proof only.
- Exact inline Native bundle: `native/selected-primary-construction.json`, SHA-256 `04b8e57e961d6b57858b90de06838a92c158ee52d02e907102894b2e1a495617`. Pinned `runtime.py offline` exited 0: `native/selected-primary-offline.log`, SHA-256 `9d07ea9bf952abedf826e4f176a0b6b8e8d71b22af1eb33919dba9a8f4b0153b`.

## Commands and next CPU work

Executed with `PYTHONDONTWRITEBYTECODE=1` and `TMPDIR=$PWD/.runtime-work/c262666-test`:

```text
.venv-cpu/bin/python work/training__C262666__NRS-484B-363-1__heavy_vehicle_driver/native/prove_school_zone.py
.venv-cpu/bin/python work/training__C262666__NRS-484B-363-1__heavy_vehicle_driver/native/build_selected.py
.venv-cpu/bin/python runtime.py offline --manifest work/training__C262666__NRS-484B-363-1__heavy_vehicle_driver/native/selected-offline-manifest.json --case training__C262666__NRS-484B-363-1__heavy_vehicle_driver__probe_03 --output .runtime-work/c262666-selected-primary-offline-r2
```

Next: build full pinned compatibility and saved-processing manifest/fixtures, Core mapping, finalizer, semantic proposals and independent audits. Construct exact probes 01, 02 and 04 and controlled speed/activation comparisons. Verify authoritative zone, calendar and beacon/sign sources and a physically suitable heavy-vehicle route locally. No original capture, physical acceptance or legal verdict is claimed.
