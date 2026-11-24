# C255863 NRS 484B.363(3) checkpoint

Status: partial. The selected school crossing-zone U-turn and five exception controls are implemented in `school_uturn.py`: no children, school not in session, outside the half-hour operation interval, operational beacon not flashing during class, and inactive sign without operational beacon. Construction creates vehicle and child actors and schedules a reversal path and beacon. The finalizer requires 900 original frames at 20 fps, stable identities, child locations, independent source hashes, zone occupancy, and a measured heading reversal. It leaves U-turn legality and children-presence interpretation unset.

Source boundary: crossing-zone designation/extent, nonadjacent school property, pupil route, independent school calendar and operation/class times, local clock, children identities/locations, beacon configuration/state and sign instruction are separately required. The 150-degree heading span is a physical realization probe, not a legal U-turn definition. No accepted exact recording exists.

Focused tests, pinned CPU preflight and scoped static check pass. Exact scoped strict fails on truthful partial status; see `cpu-strict-check.log`. Successful receipt commands and hashes appear in `result.json`.

Remaining CPU: canonical runner/config/camera capture, source-shaped positive/negative compatibility, semantic proposals, saved-only processing, and independent delivery/comparison audits.
