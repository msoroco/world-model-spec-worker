# training__C393261__LVMC-11-60-030-A5__bus_driver

Status: **partial**. No selected delivery case, original CARLA capture, source-verified designated period, or accepted recording is claimed.

Exact source: `inputs/training__C393261__LVMC-11-60-030-A5__bus_driver/assignment.json` SHA-256 `9a16ef6d44f39fd451089728127b383383a83c76161cc66adc00c9bdbf705546`; witnesses SHA-256 `226ec9ff65047ebca2c257f5ebe672c8f772bb9eb806c38ae3fea0bac4db8a55`.

The law covers a non-tour bus standing or parking at a bus stop or origin/destination point longer than the period designated for that place under LVMC 11.60.010. The frozen residential route terminus cell supports a probe, but neither the law nor cell supplies the designated period or its establishing authority. The witness explicitly says the period need not appear on a sign. The Native context therefore leaves the period null and comparison unknown. Synthetic period comparisons in CPU tests are diagnostic only.

## CPU construction checkpoint

`build-draft.py` bundles an executable `native/runner.py`, `native/geometry.py`, `native/measure.py`, and CPU tests into `draft-terminus/long_dwell/primary/construction.json`. The OpenDRIVE has a residential road, driving lane, parking lane, and route terminus marker without an invented duration. Native `execute` surveys the marker and parking lane, spawns a bus blueprint, controls approach, stop and departure, writes 600 original pose/velocity rows, a `FrameMap`, and four FFV1 camera streams, and restores the prior world in `finally`. The saved measurement derives stationary occupancy intervals and only compares them with a period when an authority source and verified designation are supplied. The primary probe is not yet a selected delivery case.

Pinned CPU proof: `PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c393261-proof" TMPDIR="$PWD/.runtime-work/c393261-tmp" .venv-cpu/bin/python runtime.py offline --manifest work/training__C393261__LVMC-11-60-030-A5__bus_driver/draft-terminus-manifest.json --case training__C393261__LVMC-11-60-030-A5__bus_driver__probe_02 --output .runtime-work/c393261-offline-01 --python "$PWD/.venv-cpu/bin/python"` passed with `offline_passed: true`, `simulation_started: false`; see `terminus-offline.log`.

Next CPU work: source and bind the actual endpoint designation and applicable period without assuming a posted duration; verify bus blueprint and activity classification conventions; implement the short-dwell comparison case, fallbacks, positive/negative compatibility and saved processing, semantic proposal, independent acceptance and comparison audits, then run the scoped strict ready gate. Native execution and physical appearance remain for the local operator.
