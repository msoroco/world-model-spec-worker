# NRS-484B-127-1 capability handoff

Exact cases: wet_gap_15, ice_gap_30.
Both exact cases passed the pinned atom gate, offline execution and actual package compatibility through analysis, native conversion, Core, Lean and video. Commands, logs, hashes and receipts are in `result.json` and `execution-manifest.json`.

The diagnostic acquisition is a three-frame retained straight-road source from this checkout. It checks software integration only; no assigned sign, signal, weather condition or following maneuver was physically acquired. The runner authors a same-lane following interval through x=15 m followed by a 30 m smooth lane change to the adjacent lane; the analyzer measures lead and ego speeds, body gap, time gap and hard deceleration only during the following interval. It records original actor/map evidence with `PipelineCapture`, four cameras and `FrameMap`, and restores the world after cleanup. The analyzer joins original source channels, audits video, measures the exact probe and writes a native result using `write_result`.

**Status: partial capability.** The pinned Core adapter has no env.ice_or_snow acquisition. Wet weather is only a commanded CARLA setting and the authored ice/snow case uses clear weather as a diagnostic control; actual surface friction, hard braking and safe following distance require native measurement.

Remaining physical measurements:
- verified wet and ice/snow road state with friction or physical surface evidence
- original leader/ego full-body gap and time gap throughout motion
- braking response and safe following judgment

No CARLA run or legal/physical acceptance is claimed.
