# C233933 NRS 484B.777(3) checkpoint

Status: partial. Four exact rider-formation probes are implemented in `abreast.py`: three and two riders on general roadway, three on exclusive-use roadway, and three on exclusive-use path. Construction creates separate identified bicycles and routes, with failure cleanup. The finalizer requires 900 original frames at 20 fps, stable rider identities and source hashes, bicycle and surface context, roadway/shoulder occupancy, positions and speeds. A .25 m longitudinal formation tolerance tests physical realization only; legal abreast and exclusive-use judgments remain unset.

Source boundary: highway, roadway and shoulder boundaries, rider occupancy, exclusive-use designation, qualifying human-powered bicycle and moped exclusion, sidewalk absence and individual riders require independent sources. No momentary-overtaking exclusion or persistence bound is assumed. No accepted exact recording exists.

Focused tests, pinned CPU preflight and scoped static check pass. Exact scoped strict fails on truthful partial status; see `cpu-strict-check.log`. Successful receipt commands and hashes appear in `result.json`.

Remaining CPU: canonical runner/config/camera capture, source-shaped positive/negative compatibility, semantic proposals, saved-only processing and independent delivery/comparison audits.
