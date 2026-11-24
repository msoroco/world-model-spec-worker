# C229398 NRS 484B.473(2) checkpoint

Status: partial. The exact displayed-light branch now has six controlled capture probes in `parked_lamps.py`: undimmed and dimmed displayed lamps without auxiliary lamps, cowl-lamp use, parking-lamp use, daytime, and unlawful-parking prerequisite control. The lawful parking, highway, vehicle, nighttime, displayed-light, beam, auxiliary-light, curb and parking-context facts remain independently source gated. The constructor commands a real vehicle route and lamp states and cleans up on failure. The finalizer measures 900 original frames at 20 fps, requires continuous stopped parking after frame 100, stable identity and source hashes, lamp states and beam aim. It leaves legal judgment unset.

Physical risk: a simulator may not expose cowl/parking lamps or beam depression. A capture without original, source-backed lamp telemetry cannot satisfy these probes. There are no accepted exact recordings. No dimming cutoff is invented.

Focused tests: six pass. Pinned CPU preflight and scoped static check pass. The exact scoped strict command exits 1 at `Preparation acceptance failed: partial/missing packages remain`, consistent with the truthful partial status. Successful proof receipts and SHA256 hashes are in `result.json`; the strict failure is in `cpu-strict-check.log`.

Remaining CPU work: canonical runner/config/camera bundle and original case capture, source-shaped positive and negative compatibility, semantic proposals, saved-only processing, and independent delivery/comparison audits. Keep partial until these exact proofs pass.
