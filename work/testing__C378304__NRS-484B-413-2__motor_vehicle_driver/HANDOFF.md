# Right-turn signal-distance capability

Three linked business-district probes request indicator onset at 95, 100, and 105 feet before the authored right-turn station. The 100-foot middle command is an engineering setpoint; actual continuously signaled distance is measured from original positions to trajectory-derived course-change onset and retains sampling brackets. Only measured evidence can support a later expected numeric outcome. The baseline is unselected.

The runner authors an intersection, frontage and freight-loading-zone objects, requests native VehicleLightState.RightBlinker, uses actual native VehicleControl, captures every original frame with supplied PipelineCapture, and retains four lossless FFV1 source views with pixel hashes. Exact offline commands/hashes are in result.json. Later use `runtime.py capture` on an operator-owned endpoint and `analyze.py --attempt PATH --output REPORT`; analysis decodes a configurable right-lamp ROI from the original view, measures brightness variation, continuous API signal, traveled distance and a same-setting follow-up decision. Saved conversion and final video composition use the supplied runtime process/render commands.

Unverified: native object rendering/use, business district physical frontage, right-lamp ROI validity, pixel visibility, controller path tracking, measured signal distance, source completeness, duration, and final video decode. Public-way and business-district status are explicit synthetic assumptions. No CARLA run or physical acceptance occurred.

The analysis checks every original trace, evidence, channel and camera frame/time join, and uses supplied worker_exchange.media.audit receipts bound to source and mapping SHA. 413(2) also computes the right-lamp pixel ROI during that same source decode. Final composed video validation remains a separate downstream check.

## Update 005 compatibility repair

The capture runner now writes canonical original CARLA/video frame identity with `FrameMap` once per recorded tick, snapshots and restores the operator-owned world with readback after independent actor/encoder cleanup, and retains a restoration receipt. The bundled analysis calls `write_result` on measured source evidence; its diagnostic output keeps setup and physical cause unresolved and maneuver completion false. Original prose assumptions remain in `context_notes`; valid synthetic Core pairs are explicit.

All 3 exact cases passed fresh offline checks. Their actual package compatibility commands ran the bundled analysis and native validation, then failed at the frozen converter: `ValueError: Unknown required atom: drv.distance_while`. Each command and hashed failure log is in `result.json`; the manifest retains its acquisition map and diagnostic fixture path. No compatibility receipt exists, so this package is **partial**, not capability ready under update 005. The unmodified mandatory atom needs upstream ontology/adapter support. The three-frame retained source with package-specific diagnostic additions tests software joins only.

The signal runner retains same-frame native weather/precipitation through the capture extra field; image ROI and turn-signal visibility still require physical source footage.

Original maneuver completion, device appearance/authority, environmental surface state where relevant, four-view framing, timing, and final encoded video remain for the operator-owned simulator run. No CARLA run, statutory judgment, or physical acceptance occurred.
