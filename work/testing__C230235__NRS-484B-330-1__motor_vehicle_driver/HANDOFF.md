# C230235 NRS 484B.330(1) checkpoint

Status: partial. Five exact designated temporary traffic control zone probes are implemented in `flagger_zone.py`: authorized stop signal with continuing and stopping driver responses; undesignated zone; unauthorized flagger; and proceed signal. Construction creates flagger and vehicle, schedules the signal/release and vehicle response, and cleans up on failure. The finalizer requires an original 900-frame 20 fps capture with stable identities, source hashes, signal governance, recipient, visibility and physical vehicle response. It leaves failure or refusal legal judgment unset.

Source boundary: designated-zone evidence and boundaries are independent of the clearly marked construction/maintenance alternative. Flagger authorization, traffic-control role, signal orientation, exact content and intended vehicle must be separately sourced; appearance alone is insufficient. No accepted exact recording exists.

Focused tests, pinned CPU preflight and scoped static check pass. Exact scoped strict fails on truthful partial status; see `cpu-strict-check.log`. Successful receipt commands and hashes appear in `result.json`.

Remaining CPU: canonical runner/config/camera capture, source-shaped positive/negative compatibility, semantic proposals, saved-only processing, and independent delivery/comparison audits.
