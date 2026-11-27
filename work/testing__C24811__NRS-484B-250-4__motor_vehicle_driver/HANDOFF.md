# C24811 NRS 484B.250(4) CPU delivery handoff

The exact C24811 cell is `blind_intersection` / `travel` / `traffic_light`. The selected branch is post-stop interactions under complete signal inoperability. The six selected cases and five comparisons in `case-plan.json` cover the stop-reference hierarchy (marked line, near-side crosswalk if no line, nearest-view point if neither), a vehicle with a prior completed stop, a vehicle within the intersection, no priority vehicle, and yielding versus entering before clearance. The statute supplies no numeric cautiousness cutoff.

## Source and construction boundary

`native_signal.py` requires a source-hashed reviewed original site packet showing the frozen traffic-light control, installed and uncovered governing vehicular heads, complete inoperability at actual entry, all entrance/head identity, a blind sightline with reviewed physical occluder, source-surveyed stop references, connected ego/other routes, and through-highway context. The runner requires a hashed Native operator module and does not import CARLA in CPU checks. Capture retains 900 synchronized 20 Hz frames and four original camera views. Physical and legal outcomes remain unresolved. Frozen accepted evidence inventory has no recordings; every selected case addresses that gap.

## CPU proofs

- Twelve current primary/fallback offline constructions and twelve positive/negative compatibility checks passed.
- Six recorded-only synthetic saved processing positives and six missing-source feedback negatives passed.
- Six physical/lifecycle diagnostic fixture sets passed; original capture and owner release are not claimed.
- Six selected delivery positive/missing-source negative audits and five controlled comparison audits passed on synthetic fixtures.
- Thirteen focused unit tests passed, including wrong frozen control, changed source bytes, partial signal operation, missing stop/occluder, frame join, hierarchy and interaction tests.
- `queue-proposal.json` lists six exact original-only delivery commands and five comparison audit commands for lead integration after the scoped strict gate.

## Resume and local delivery

Run `.venv-cpu/bin/python worker_check.py --assignment testing__C24811__NRS-484B-250-4__motor_vehicle_driver --complete --require-delivery-ready`. Local dispatch must supply reviewed original signal site/operator packets and then independently inspect original motion, stop position, inoperability at entry, camera visibility, video decode, physical clearance, and comparison isolation. Do not treat CPU fixtures or requested policies as legal acceptance.
