# 400(2)(a) pilot capability handoff

Two exact nonbaseline cases compare inner and outer approach positions on a two-directional synthetic intersection. The baseline is a definition only. The exact input law and witness govern; public dedication, access, and non-alley status remain explicit synthetic assumptions.

The shared runtime selftest passed separately. Run the exact cases with `runtime.py offline` using execution-manifest.json. A later operator may run `runtime.py capture` against an already-owned CARLA endpoint, then `analyze.py --attempt PATH --output REPORT` on the retained native samples. Capture uses the supplied PipelineCapture; conversion/rendering remain the supplied runtime process/render commands. No simulator was run here.

Capability questions: native map turn continuity, ego controller tracking, right-half full footprint, four-view visibility, final duration and delivered channel coverage. The capability report requests repair at the same frozen setting if measured motion fails. No physical or legal acceptance is claimed.
# Update 005 pilot repair

The capture path writes canonical `video_frame`, `carla_frame`, `native_frame` and
`time_s` through `FrameMap.append` on each recorded tick. The analyzer checks
original trace, capture, physical sample, channel and frame-map joins and writes
the native execution result through `write_result`. It leaves setup, physical
cause, camera visibility and legal meaning unconfirmed. The runner snapshots the
operator's original world and attempts every owned encoder/actor cleanup action
before `world_restore.restore` with readback, saving `world-restore.json`. A normal
incomplete maneuver is retained for analysis; a failed capture has extraction
confirmation false. CPU client and frame-writer doubles exercise these paths.

Both exact cases pass `runtime.py offline` after update 005. Their compatibility
commands and hashed failure logs are in `result.json` and `tests/`. The diagnostic
fixture uses three retained frames plus explicitly synthetic pilot channels and
map context. It does not demonstrate pilot movement, geometry or visibility.
Analysis, native result validation and source video decode complete. Conversion
then raises `ValueError: Unknown required atom: drv.turning` in the frozen
`traffic_spec_adapter.atom_contract.required_coverage` for both cases. The
mandatory `st.one_way_roadway` is also absent from the frozen ontology, and
`st.lane_enters` needs a closed signed original execution that the diagnostic
compatibility command cannot create. No mandatory requirement was deleted or
renamed. The package remains partial pending a legitimate runtime capability
extension or operator-owned physical attempt; no CARLA run or physical acceptance
is claimed.
