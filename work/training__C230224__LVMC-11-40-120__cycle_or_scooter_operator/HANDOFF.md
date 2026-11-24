# training__C230224__LVMC-11-40-120__cycle_or_scooter_operator

Status: **partial**. Exact `probe_01` is selected for travel on the provided adjacent path. Its survey-gated Native primary passes the pinned offline check. Source-shaped measurement diagnostics pass; full CPU delivery proofs remain open.

Exact LVMC 11.40.120 requires riders of bicycles, electric bicycles and electric scooters to use a usable adjacent path, and not the roadway, when one is provided. The frozen witness names affirmative path use and prohibited roadway use. The full-train accepted membership is empty. A path polygon does not prove usability; saved measurement keeps reviewed path condition separate from device footprint occupancy and offers no legal verdict.

## Implemented checkpoint

- `native/selected_primary/runner.py` checks exact case identity without CARLA, then requires a reviewed survey for the path, roadway, rideable device, attached rider and four cameras. The capture path requests 20 Hz travel, writes 600 original frame identities, source device/rider IDs, device bounding-box footprints and measured velocity, plus four source camera videos. Physical support and pixels require local review.
- `native/measure_path.py` joins 600 raw Native trace rows to the frame map and four decoded camera files. It requires byte-hashed original cameras at the capture profile resolution and reviewed path surface, continuity, adjacency, obstruction, usability and roadway boundaries. It reports moving-frame path/road occupancy and obstruction area without a legal cutoff.
- `native/prove_path.py` passed four synthetic variants: path clear (600 path frames), roadway with path (600 road frames), path obstructed (600 path frames, reviewed unusable), and outside both. It rejected eight mutations of frame, provenance, rider, camera hash, source, subtype, geometry and usability. Log: `native/path-proof.log`, SHA-256 `3105ad172a7407c9b2657cb792fa9d47af44659d5f609c62ebac7febc0a32748`. This is software proof only.
- Exact inline Native bundle: `native/selected-primary-construction.json`, SHA-256 `c033299368bc6bd40fe1642eb83e9774884b89230ba71f509c2e9448d4def2e6`. Pinned `runtime.py offline` exited 0: `native/selected-primary-offline.log`, SHA-256 `0c79012951a7540e1ce7eac0081f78fd3387227239eaceea0f22934cf8593a12`.

## Commands and next CPU work

Executed with `PYTHONDONTWRITEBYTECODE=1` and `TMPDIR=$PWD/.runtime-work/c230224-test`:

```text
.venv-cpu/bin/python work/training__C230224__LVMC-11-40-120__cycle_or_scooter_operator/native/prove_path.py
.venv-cpu/bin/python work/training__C230224__LVMC-11-40-120__cycle_or_scooter_operator/native/build_selected.py
.venv-cpu/bin/python runtime.py offline --manifest work/training__C230224__LVMC-11-40-120__cycle_or_scooter_operator/native/selected-offline-manifest.json --case training__C230224__LVMC-11-40-120__cycle_or_scooter_operator__probe_01 --output .runtime-work/c230224-selected-primary-offline
```

Next: construct full pinned compatibility and saved-processing manifest and fixtures, Core mapping, finalizer, semantic proposals and independent audits. Implement exact `probe_02` roadway travel on the same reviewed topology and a controlled path-choice comparison. Local survey must verify actual adjacent path usability, physical rideable device and attached rider, route and pixels before source review. No original capture, physical acceptance, or legal verdict is claimed.
