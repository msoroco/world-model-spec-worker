# training__C190631__LVMC-11-30-090__pedestrian

Status: **partial**, current runtime. Both exact walking-surface drafts pass CPU offline construction. No CARLA recording or physical acceptance is claimed.

## Source and scope

LVMC 11.30.090 states: “Where sidewalks are provided it shall be unlawful for any pedestrian to walk along and upon an adjacent roadway.” C190631 fixes the pedestrian overpass / travel / sidewalk cell. The accepted-recording membership is empty. The frozen witness is a conditional, low-confidence proposed match; it does not prove sidewalk provision, pedestrian-use purpose, or adjacency. State-law sidewalk-obstruction permission and its municipal interaction remain legal context for review. No numeric legal distance, duration, heading, or occupancy cutoff was invented. The two exact cases compare the same afoot route on the sidewalk (probe_01) and adjacent roadway (probe_02).

## Constructed CPU path

`native/geometry.py` authors a 100 m upper road at z=8 with a 3.5 m roadway, 0.5 m shoulder and 2 m sidewalk, plus a crossing lower 60 m road at z=0. `native/runner.py` surveys three Native waypoints on each of the upper roadway, upper sidewalk and lower road, requiring correct road and lane IDs and grade separation before capture. Probe_01 spawns the walker at y=-5; probe_02 at y=-1.75. Both apply the same 2 m/s along-road control for 600 ticks at 20 Hz and use four synchronized FFV1 cameras. Original frame IDs, timestamps, actor ID, pose, velocity, heading and four bounding-box footprint corners are retained. The runner snapshots and restores the world, destroys owned actors, and seals only after all 600 frames and successful camera encodes. This is authored code; CARLA has not run.

`native/measure.py` requires original 600-frame timing, Native source surveys, polygons and four footprint corners at each frame. It measures full-footprint surface occupancy intervals, longitudinal versus lateral travel and path length without a legal verdict. `comparison_meter.py` requires identical source geometry and comparable route length, then checks the deliberate walking-surface difference. The comparison is a synthetic source-meter proof, not yet an independent delivery comparison audit.

Current draft manifest SHA-256: `180fc6760d669c600631a6b7b6b81b3b6bec1be68fcce321e7d36cc06d27c874`. Probe_01 construction SHA-256: `78bd2f17bd1f17c218d3234637be113801075a393bc551742d671d361ef49f57`; probe_02: `896822bddc3689af8ff814ffab931f04ce9f638772c34015211ddd791e243baf`. Pinned runtime manifest: `5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3`.

## Retained CPU proofs

- `runtime.py offline --manifest work/training__C190631__LVMC-11-30-090__pedestrian/draft-roadway-manifest.json --case training__C190631__LVMC-11-30-090__pedestrian__probe_01 --output .runtime-work/c190631-offline-sealed-01 --python $PWD/.venv-cpu/bin/python`: exit 0; `probe-01-offline.log`.
- Same command for `probe_02` and `.runtime-work/c190631-offline-sealed-02`: exit 0; `probe-02-offline.log`.
- `.venv-cpu/bin/python -B work/training__C190631__LVMC-11-30-090__pedestrian/prove-measure.py`: exit 0; roadway and sidewalk positive source-shaped fixtures; missing frame, missing footprint, missing provided sidewalk, missing Native survey and wrong lower-road source all rejected. `roadway-measure-proof.log` SHA-256 `ec4d64f311fd65e800b3ed06bc9bf1f98c51982f4ff2bdebed4fde9bc59c4b85`.
- `.venv-cpu/bin/python -B work/training__C190631__LVMC-11-30-090__pedestrian/prove-comparison.py`: exit 0; positive controlled difference, mismatched geometry, absent surface difference and missing footprint rejected. `comparison-meter-proof.log` SHA-256 `552b71f62bc5e95d523da3f0a80fdf4dd08a4bc96b7b12cb750697a36f0d6071`.
- `PYTHONPATH=$PWD/work/training__C190631__LVMC-11-30-090__pedestrian/native .venv-cpu/bin/python -B -m unittest discover -s work/training__C190631__LVMC-11-30-090__pedestrian/native/tests -v`: three tests pass, including wrong-lane rejection. `native-cpu-tests.log`.
- `.venv-cpu/bin/python -B worker_check.py --assignment training__C190631__LVMC-11-30-090__pedestrian --complete`: static partial check passed after this construction update. All runtime imports were run with `SCENARIO_PIPELINE_OUTPUT_ROOT` under `.runtime-work/`.

## Exact next CPU work

Promote both drafts into selected executable cases with measurement contracts and source-hashed fixture recipes. Author saved-only finalization, positive and missing-source compatibility, recorded-only processing, semantic proposals, physical-completion and lifecycle tests, independent delivery acceptance and full comparison audits. Assess and test any justified physical fallback. The four-camera profile and actual sidewalk provision/purpose, map connectivity, body motion, pixels and Native seal need local CARLA and independent source review. Keep result partial until the exact strict assignment gate passes.
