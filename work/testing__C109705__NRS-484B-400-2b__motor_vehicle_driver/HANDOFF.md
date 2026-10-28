# NRS-484B-400-2b capability handoff

Exact cases: right_exit, left_exit. Each case passed pinned atom preflight, offline execution, and full package compatibility through analysis, native conversion, Core, Lean, and video. The per-case commands, logs, receipts and hashes are recorded in `result.json` and `execution-manifest.json`.

The diagnostic fixture is synthetic acquisition adapted from the current checkout's pinned compatibility example. Its three-frame straight-road trace checks the software pipeline and does not demonstrate the assigned maneuver or legal condition. The executable runner creates the authored native road and actors, captures original telemetry and four camera streams with `PipelineCapture` and `FrameMap`, and restores world settings after independent cleanup. The analyzer joins captured channels and original evidence, computes mode-specific measurements, audits video, and calls `write_result`.

Preparation status: **partial** (capability). The pinned Core adapter cannot acquire st.one_way_roadway, and the three-frame straight-road diagnostic cannot validate the two-directional junction, exit half-roadway, or completed left turn. The native turn experiment is authored but unmeasured.

Unresolved physical measurements:
- native two-directional junction and outgoing half-roadway inventory
- full vehicle body position relative to exit centerline after turn
- actual controller completion and camera framing

No CARLA run or physical/legal acceptance is claimed.
