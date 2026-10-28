# One-way direction capability

The two exact nonbaseline cases use the same two-lane eastbound road and authored OneWay signal. One native controller follows the designated eastbound direction; the other drives westbound along the same physical right-side lane, retaining full original body, heading, control, sign inventory, and four lossless source views. The baseline is unselected. Public-way status and designation are explicit synthetic assumptions.

Run each exact offline command in result.json. A later operator may use `runtime.py capture` against an already-owned CARLA endpoint, then `analyze.py --attempt PATH --output REPORT`. This measures actual travel direction, full-body roadway occupancy, and native sign inventory; rendered sign visibility and its governed extent still need saved-source review. Shared PipelineCapture, process, and render supply capture/conversion/video processing. No CARLA episode or physical acceptance occurred.

The analysis checks every original trace, evidence, channel and camera frame/time join, and uses supplied worker_exchange.media.audit receipts bound to source and mapping SHA. 413(2) also computes the right-lamp pixel ROI during that same source decode. Final composed video validation remains a separate downstream check.

## Update 005 compatibility repair

The capture runner now writes canonical original CARLA/video frame identity with `FrameMap` once per recorded tick, snapshots and restores the operator-owned world with readback after independent actor/encoder cleanup, and retains a restoration receipt. The bundled analysis calls `write_result` on measured source evidence; its diagnostic output keeps setup and physical cause unresolved and maneuver completion false. Original prose assumptions remain in `context_notes`; valid synthetic Core pairs are explicit.

All 2 exact cases passed fresh offline checks. Their actual package compatibility commands ran the bundled analysis and native validation, then failed at the frozen converter: `ValueError: Unknown required atom: drv.wrong_way`. Each command and hashed failure log is in `result.json`; the manifest retains its acquisition map and diagnostic fixture path. No compatibility receipt exists, so this package is **partial**, not capability ready under update 005. The unmodified mandatory atom needs upstream ontology/adapter support. The three-frame retained source with package-specific diagnostic additions tests software joins only.

Original maneuver completion, device appearance/authority, environmental surface state where relevant, four-view framing, timing, and final encoded video remain for the operator-owned simulator run. No CARLA run, statutory judgment, or physical acceptance occurred.
