# C229439 LVMC 11.52.340 checkpoint

Status: partial. Five exact municipal-space parking probes are implemented in `city_space.py`: non-City vehicle in a designated and duly posted City space; City vehicle control; missing Council designation; missing official posting; and parking outside the governed space. The constructor places an exact parking device and vehicle route, and cleans up both on failure. The finalizer requires an original 900-frame 20 fps capture with stable participants, device text, source hashes, parked interval and governed-space occupancy. Legal judgment and unresolved City-vehicle scope remain unset.

Source boundary: City location, Council designation, authoritative vehicle status, official device instruction and posting, governed-space geometry, parking purpose, loading and NRS definition scope require separate source hashes. A City-looking livery or plate cannot substitute for authority. No accepted exact recording exists.

Focused tests, pinned CPU preflight and scoped static check pass. Exact scoped strict check fails on truthful partial status; see `cpu-strict-check.log`. Successful receipt commands and hashes appear in `result.json`.

Remaining CPU: canonical runner/config/camera capture, source-shaped positive/negative compatibility, semantic proposals, saved-only processing, and independent delivery/comparison audits.
