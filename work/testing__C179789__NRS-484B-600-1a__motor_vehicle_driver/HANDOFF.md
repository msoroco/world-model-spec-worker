# Reasonable-speed capability sweep

The exported batch_pipeline.sweeps.expand_sweeps froze four speed commands, 5–20 m/s at 5 m/s spacing, with clear weather and adjacent-lane traffic held fixed. These are physical coverage targets; “reasonable or proper” remains unresolved and no expected judgment labels are assigned. The baseline is unselected.

The runner authors the paved two-lane 500m road, controls the ego and traffic vehicle through native VehicleControl, records every original tick using supplied PipelineCapture, retains full bodies/weather/control and four lossless FFV1 source views. Exact offline commands and hashes are in result.json. A later operator may use `runtime.py capture` against an owned endpoint, then `analyze.py --attempt PATH --output REPORT`; it measures realized speed over native x=100..300m, traffic speed, completion, and a same-setting follow-up decision. Saved conversion/rendering use shared runtime process/render.

Physical road surface, achieved speed, traffic motion, visibility, duration, source completeness, and decoded videos remain unverified. Public-highway status is an explicit synthetic assumption. No CARLA run or physical acceptance occurred.

The analysis checks every original trace, evidence, channel and camera frame/time join, and uses supplied worker_exchange.media.audit receipts bound to source and mapping SHA. 413(2) also computes the right-lamp pixel ROI during that same source decode. Final composed video validation remains a separate downstream check.

## Update 005 compatibility repair

The capture runner now writes canonical original CARLA/video frame identity with `FrameMap` once per recorded tick, snapshots and restores the operator-owned world with readback after independent actor/encoder cleanup, and retains a restoration receipt. The bundled analysis calls `write_result` on measured source evidence; its diagnostic output keeps setup and physical cause unresolved and maneuver completion false. Original prose assumptions remain in `context_notes`; valid synthetic Core pairs are explicit.

All 4 exact cases passed fresh offline checks. Their actual package compatibility commands ran the bundled analysis and native validation, then failed at the frozen converter: `ValueError: Unknown required atom: drv.queue_behind`. Each command and hashed failure log is in `result.json`; the manifest retains its acquisition map and diagnostic fixture path. No compatibility receipt exists, so this package is **partial**, not capability ready under update 005. The unmodified mandatory atom needs upstream ontology/adapter support. The three-frame retained source with package-specific diagnostic additions tests software joins only.

The numeric runner calls the shipped RGB/instance contrast calibration before recording and places same-frame environmental measurements in `PipelineCapture.capture(extra=...)`. It queries native scene object names but has no verified material asset paths for this generated 500 m road; the retained dry-asphalt surface helper encodes different 10 m/7 m dimensions and is not transplanted. Native surface appearance and ice/snow status stay unresolved.

Original maneuver completion, device appearance/authority, environmental surface state where relevant, four-view framing, timing, and final encoded video remain for the operator-owned simulator run. No CARLA run, statutory judgment, or physical acceptance occurred.
