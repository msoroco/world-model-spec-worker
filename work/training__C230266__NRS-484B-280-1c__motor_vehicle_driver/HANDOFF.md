# NRS 484B.280(1)(c), C230266 motor vehicle driver

Status: **partial**. The frozen road/travel/pedestrian cell and witness support a separate pedestrian on the road, but no accepted recording is listed. The statutory text also covers transit stops or boarding and school zones or crosswalks. Those alternatives are still pending exact controlled cases. “Proper caution” and “near” have no statutory numeric threshold in this source. The first draft uses the on-road alternative and does not decide legal compliance.

## This checkpoint

- `native/caution_meter.py` measures a 600-frame, 20 Hz source packet with distinct vehicle/pedestrian IDs, road boundary, actor poses, speed, line of sight, and separate actual driver observation. It verifies a canonical SHA-256 trace hash and frame/video joins. Distance, speed change and time to conflict are descriptive measurements only.
- `native/prove_caution_meter.py` passed two 30-second synthetic samples (slow request and maintained speed) and rejected six altered packets: no observation, no observation provenance, off-road pedestrian, short trace, broken video join and stale source hash. Proof: `native/caution-meter-proof.json`, SHA-256 `900fd4301787f8b3b99b7d535082c9c57c788216aef4aff8e51d00a55430f433`. This is a CPU software fixture, not original Native conduct.
- `native/draft-primary/runner.py` contains an unselected exact probe 1 Native capture proposal with a sourced road/pedestrian spawn, observed-distance speed request, 600 frames at 20 Hz, four synchronized source cameras, `PipelineCapture`, `FrameMap`, actor pose/control trace, and world restore. It intentionally writes actual driver observation and geometric visibility as unknown; they require independent original sources. No CARLA execution is claimed.
- `native/build_draft.py` bound the inline construction at `native/unselected-road-pedestrian-construction.json`, SHA-256 `e63abaf07e33e00e0008a7965a9a6710637b2e3a4986fcd3514fd49eddf811a0`. Pinned `runtime.py offline` passed its exact 30-second/four-camera check and four offline tests. Log: `native/draft-primary/offline.log`, SHA-256 `01dd37a493507d798508481a446467b8c4cf7f7ba0c76a0a9549fa044d751ece`. The unselected manifest is `draft-road-pedestrian-manifest.json`.
- `native/measurement-contract.json` lists the raw sources and result fields. `case-plan.json.source_observation_mapping` maps every exported planning term while marking transit, school and crosswalk sources pending.

Commands run from repository root:

```text
.venv-cpu/bin/python runtime.py preflight
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C230266__NRS-484B-280-1c__motor_vehicle_driver/native/prove_caution_meter.py
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C230266__NRS-484B-280-1c__motor_vehicle_driver/native/build_draft.py
.venv-cpu/bin/python runtime.py offline --manifest work/training__C230266__NRS-484B-280-1c__motor_vehicle_driver/draft-road-pedestrian-manifest.json --case training__C230266__NRS-484B-280-1c__motor_vehicle_driver__probe_1 --output .runtime-work/c230266-nrs280-1c-draft-primary
.venv-cpu/bin/python worker_check.py --assignment training__C230266__NRS-484B-280-1c__motor_vehicle_driver --complete
```

## Next CPU work

Obtain and bind an original road boundary, pedestrian classification and driver-control source. Establish actual observation independently of line of sight or requested speed. Promote probe 1 only after source review; build probe 2 and separate transit and school/crosswalk alternatives with controlled comparisons. Add selected exact offline, positive/negative compatibility, saved-only finalization, fallbacks, independent acceptance and comparison audits. Run the assignment-scoped strict gate before changing status to ready. Physical Native motion, actual pixels and canonical acceptance remain unverified.
