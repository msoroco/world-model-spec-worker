# NRS-484B-223-1b capability handoff

Exact cases: signal_before, signal_at_move. Each case passed pinned atom preflight, offline execution, and full package compatibility through analysis, native conversion, Core, Lean, and video. The per-case commands, logs, receipts and hashes are recorded in `result.json` and `execution-manifest.json`.

The diagnostic fixture is synthetic acquisition adapted from the current checkout's pinned compatibility example. Its three-frame straight-road trace checks the software pipeline and does not demonstrate the assigned maneuver or legal condition. The executable runner creates the authored native road and actors, captures original telemetry and four camera streams with `PipelineCapture` and `FrameMap`, and restores world settings after independent cleanup. The analyzer joins captured channels and original evidence, computes mode-specific measurements, audits video, and calls `write_result`.

Preparation status: **ready** (capability). Executable lane change and signal lead experiment is prepared with a target-lane actor. Readiness is for capability testing only; the straight-road diagnostic does not establish safe movement.

QA repair: analysis now measures original XY path length from signal onset to first 0.1 m lateral movement and separately records the first full-body lane-boundary crossing. A missing diagnostic signal remains explicit as a null onset and physical cause remains unconfirmed. Both exact cases passed renewed preflight, offline and full compatibility with rebound receipts.

Unresolved physical measurements:
- native lane IDs, signal onset and first lateral movement
- target-lane actor full-body gap and time to conflict
- operator judgment of safety and public-road context

No CARLA run or physical/legal acceptance is claimed.
