# NRS 484D.100(1) at C179824: CPU checkpoint

Actor `motor_vehicle_driver`, frozen `paved_road` / `travel` / `traffic_control_device` cell. The frozen witness targets subsection (c): a governing official traffic-control device directs lamp use. The law independently includes (a) the exact sunset/sunrise half-hour interval, (b) insufficient light or unfavorable conditions that prevent 1,000-foot-ahead discernibility, class-specific chapter 484D equipment requirements, and referenced parked-vehicle exceptions. No accepted recordings were supplied. These branches and dependencies are retained in `case-plan.json`; weather alone is not treated as proof of discernibility.

## Construction and CPU evidence

- `native/geometry.py` authors a 160 m paved-road OpenDRIVE draft, driving lane and HEADLAMPS ON sign. `native/runner.py` surveys original sign/lane readback, moves an ordinary motor-vehicle blueprint through the sign's requested extent, sets paired light states, records CARLA light-state readback per original frame, and captures four synchronized 1280×720 FFV1 cameras at 20 Hz for 600 frames. It uses original `FrameMap`, restores the world and destroys owned actors. No Native execution or pixel observation occurred.
- `build_draft.py` creates lamp-on `controlled_1` and lamp-off `controlled_2` source-hashed primary bundles in `draft-lamp-device-manifest.json`. Construction SHA-256 values: `e38e18399e7d973ea39f483034f75cd5b63b9f742f50a7cefd9cb66979558d42` and `f8942cf65be76bc26839d9a9ab7a2c35d919ba891661ccce97dd9de25ed97e63`. Both pass pinned `runtime.py offline` with `.venv-cpu/bin/python`; offline logs each hash to `38c9d24deedd01f9fa688c210462c111e357265e53fbde26c33f2d9ccdf556d5`.
- `lamp_saved_measure.py` requires separately hashed highway, class, official directive content/authority/placement/timing sources. It joins original lamp trace, `FrameMap` and OpenDRIVE hash, then counts governed frames with headlamp and position-lamp settings. `prove_lamp_saved_measure.py` passes three 600-frame/20-Hz synthetic positives and nine damaged-source negatives in normal and optimized Python; both proof logs hash to `1a80de5fe7dd2d9553acdb7e41083d172ca980baef6d2b65e2e92e799aa99bb1`.
- `.venv-cpu/bin/python worker_check.py --assignment training__C179824__NRS-484D-100-1__motor_vehicle_driver --complete` passes for this partial checkpoint.

The Native draft leaves official authority, Nevada highway, vehicle class, directive timing and parked-vehicle source fields null. That is intentional fail-closed behavior until independently sourced; OpenDRIVE sign metadata and lamp-setting bits do not prove official placement, emitted light, equipment sufficiency or compliance.

## Exact remaining CPU work

1. Decompose and implement the exact (a) sunset/sunrise, (b) 1,000-foot discernibility, and parked-exception branches. Obtain source-backed class-specific lamp requirements without inventing sufficiency from LowBeam/Position flags.
2. Complete source-reviewed Native saved finalization, four-video decode and actual-pixel audit, positive/missing-source compatibility and recorded-only processing for each final selected case.
3. Add physically triggered fallback constructions, semantic/Core proposals, independent delivery and controlled-comparison audits; bind final manifests and run the assignment strict ready gate.

Status remains `partial`. No physical, legal or accepted-membership result is claimed.
