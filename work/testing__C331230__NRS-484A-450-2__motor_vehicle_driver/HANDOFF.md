# C331230 NRS 484A.450(2) checkpoint

Status: partial. Four exact near-side crosswalk probes are implemented in `near_crosswalk.py`: marked halt and rolling (matching two frozen accepted metadata case names), plus unmarked halt and rolling. Construction creates the governed approach and vehicle route, with cleanup on failure. The finalizer requires 900 original frames at 20 fps, stable identities and source hashes, vehicle-front position, first crosswalk entry, physical cessation before entry and subsequent crossing. It leaves stop-before-crosswalk legal judgment unset.

Evidence boundary: two accepted 900-frame metadata records are preserved in `case-plan.json`, but original traces/videos are absent here; metadata does not prove physical stopping or crossing. Sign orientation/governance and near-side crosswalk boundaries from opposing sidewalks need independent sources. No minimum stop duration is inferred.

Focused tests, pinned CPU preflight and scoped static check pass. Exact scoped strict fails on truthful partial status; see `cpu-strict-check.log`. Successful receipt commands and hashes appear in `result.json`.

Remaining CPU: canonical runner/config/camera capture or original trace review, source-shaped positive/negative compatibility, semantic proposals, saved-only processing, and independent delivery/comparison audits.
