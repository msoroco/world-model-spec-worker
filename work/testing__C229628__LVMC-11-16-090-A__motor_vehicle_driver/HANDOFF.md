# C229628 LVMC 11.16.090(A) checkpoint

Status: partial. Four exact two-vehicle probes are implemented in `contest_aid.py`: an ego start cue preceding another motorist's candidate contest, no cue control, no underlying candidate contest control, and off-highway control. Construction creates and routes both vehicles, schedules cue and other start, and cleans up on failure. The finalizer requires a source-bound original 900-frame capture at 20 fps with stable identities, cue timing, route/lane and highway context, speeds, accelerations and positions. It leaves contest and aid/abet legal judgments unset.

Physical risk: neither coordination nor high speed proves aid, abet or contest. Source hashes separately bind participants, qualifying vehicles, municipal jurisdiction, highway, lane marking, episode, cue conduct/timing and unresolved legal meanings. No accepted exact recording exists.

Focused tests, pinned CPU preflight and scoped static check pass. Exact scoped strict fails on truthful partial status; see `cpu-strict-check.log`. Successful receipt commands and hashes appear in `result.json`.

Remaining CPU: canonical runner/config/camera capture, source-shaped positive/negative compatibility, semantic proposals, saved-only processing, and independent delivery/comparison audits.
