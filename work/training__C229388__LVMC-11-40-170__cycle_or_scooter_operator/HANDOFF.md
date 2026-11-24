# training__C229388__LVMC-11-40-170__cycle_or_scooter_operator

Status: **partial**. Exact `probe_01` is selected for the source-witness sidewalk rack branch. Its survey-gated Native primary passes the pinned offline check. The software source-measurement diagnostic passes; complete CPU delivery proofs remain open.

The exact LVMC 11.40.170 text in `case-plan.json` permits roadway against curb and sidewalk placement in a supporting rack, against a building, or at the curb, with least pedestrian obstruction. The witness selects the supporting-rack branch. No accepted full-train membership exists for this assignment. A rack by itself does not establish least obstruction; the saved measurement reports footprint overlap and pedestrian-corridor surface gap without a legal cutoff or verdict.

## Implemented checkpoint

- `native/selected_primary/runner.py` checks exact case identity without importing CARLA, then requires a reviewed map survey for device, operator, rack and four camera spawns. The capture path records 600 original frame identities at 20 Hz, source actor IDs, device bounding-box footprints and velocities, and four source camera videos. It leaves reviewed placement geometry and pixel visibility for source review.
- `native/measure_parking.py` joins all 600 frames, raw Native trace and four decoded source cameras to a source-reviewed context. It measures rack intersection and pedestrian-corridor overlap/gap only during rest frames. Original evidence requires profile camera resolutions and camera byte hashes. It rejects absent reviewed sources and provenance mismatches.
- `native/prove_parking.py` passed four synthetic geometry variants: rack clear (600 rack, zero corridor overlap), rack and corridor overlap (600 each), outside rack (zero rack), and across pedestrian path (600 corridor). It rejected seven frame, provenance, actor, camera-hash, rack-source, subtype and geometry mutations. Log: `native/parking-proof.log`, SHA-256 `2f92d51395568da9641be9111f626a1162fa1633cdc8f34eb5e6ba6320a418f0`. These are software diagnostics, not physical evidence.
- Exact inline Native bundle: `native/selected-primary-construction.json`, SHA-256 `c1b5c00996c4765fa7763d81bd5fa9d3390602ce0035dd26529585dfc7c04238`. Pinned `runtime.py offline` exited 0: `native/selected-primary-offline.log`, SHA-256 `182a23ece0d45c31a5fcb1bf2e31a25aea124ba8e2821651bdc74647ef4231e8`.

## Commands and next CPU work

Executed with `PYTHONDONTWRITEBYTECODE=1` and `TMPDIR=$PWD/.runtime-work/c229388-test`:

```text
.venv-cpu/bin/python work/training__C229388__LVMC-11-40-170__cycle_or_scooter_operator/native/prove_parking.py
.venv-cpu/bin/python work/training__C229388__LVMC-11-40-170__cycle_or_scooter_operator/native/build_selected.py
.venv-cpu/bin/python runtime.py offline --manifest work/training__C229388__LVMC-11-40-170__cycle_or_scooter_operator/native/selected-offline-manifest.json --case training__C229388__LVMC-11-40-170__cycle_or_scooter_operator__probe_01 --output .runtime-work/c229388-selected-primary-offline
```

Next: build the full pinned compatibility manifest and positive/negative saved-processing fixture from raw trace/cameras; map measurements to Core and add exact semantic proposals, finalizer and independent audits. Implement exact `probe_02`, controlled comparison and any additional supported position alternatives after source/cell review. Test the survey against a local map and source-review actual pixels/geometry during the GPU phase. No physical acceptance, original recording or legal verdict is claimed.
