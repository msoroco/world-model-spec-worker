# training__C190631__LVMC-11-30-090__pedestrian

Status: **partial**. A survey-gated roadway Native capture path passes CPU offline checks. It has not run in CARLA; no delivery-ready case or accepted recording is claimed.

Exact law: “Where sidewalks are provided it shall be unlawful for any pedestrian to walk along and upon an adjacent roadway.” The frozen cell is pedestrian overpass / travel / sidewalk. The comparison varies walking surface. The statute supplies no minimum path length or duration; retained distance, heading and occupancy are observations for review. There are no accepted membership IDs.

## Native construction and source measurements

- `native/geometry.py` builds a 100 m elevated OpenDRIVE road at z=8 with a 3.5 m roadway, 0.5 m shoulder and 2 m adjacent sidewalk. `native/runner.py` requires Native readback at three positions on each surface, including lane IDs and elevation, before any walker capture. CPU tests reject a wrong-lane survey. CARLA support and physical geometry remain unverified.
- The Native path spawns a pedestrian, applies 2 m/s walker control for 600 ticks at 20 Hz, retains original poses and Native frame/time IDs through `FrameMap`, and encodes four synchronized FFV1 camera streams. It snapshots and restores the operator world and destroys owned actors. Runtime execution has not been attempted.
- `native/measure.py` requires 600 original pose rows, 20 Hz timing, provided adjacent sidewalk context and Native survey. It reports roadway/sidewalk occupation intervals and longitudinal/lateral distance without a legal verdict. Original surface polygons remain subject to physical inspection.
- Draft manifest construction SHA-256 `3cda3decccea9e71bf4d9ea19eccd826cff7623f649c2ef45f2be9b9bcd2894a`; pinned runtime `ade64f2acdaf6d4b653c38f49b71f8c4bd2cf4a985cab7313f160b97b06c3d90`.

## CPU proofs

- `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c190631-proof TMPDIR=$PWD/.runtime-work/c190631-tmp .venv-cpu/bin/python runtime.py offline --manifest work/training__C190631__LVMC-11-30-090__pedestrian/draft-roadway-manifest.json --case training__C190631__LVMC-11-30-090__pedestrian__probe_02 --output .runtime-work/c190631-offline-05 --python $PWD/.venv-cpu/bin/python` passed; three offline Native tests passed; `roadway-offline.log` SHA-256 `d7dad8867f17dac293eec29abd28c5a6742894f90b3e0e94479acaefecba7437`. No simulation started.
- `.venv-cpu/bin/python work/training__C190631__LVMC-11-30-090__pedestrian/prove-measure.py` passed synthetic 600-frame roadway and sidewalk cases; missing frame, missing provided sidewalk and missing Native survey each rejected. `roadway-measure-proof.log` SHA-256 `8b10e8cab068a5df605aa753b4ddc2a743a36660bb5d6b9651589c81c75798ed`. Fixtures remain in `.runtime-work/`; they establish software behavior only.

## Open work

Physically run the survey-gated Native path in local CARLA, inspect walker motion, sidewalk continuity, roadway occupation and four-camera pixels. Complete the sidewalk counterpart under the same fixed conditions, current-runtime source-bound positive/negative compatibility and saved processing, Core finalization, semantic proposals, independent acceptance/comparison audits and risk candidates. Keep this assignment partial until all CPU proofs and the strict scoped gate pass.
