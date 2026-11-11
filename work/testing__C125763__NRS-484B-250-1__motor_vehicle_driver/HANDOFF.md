# C125763 CPU handoff — NRS 484B.250(1)

Status: **partial**. The frozen selected branch is other-first entry at a median-opening crossing, in a yield-sign cell. Exact NRS 484B.250(1) excludes intersections controlled by official traffic-control devices except as provided in subsection 4. Other-first entry at this sign is an observation, not a violation finding. Frozen `evidence.json` has no accepted recordings; no reuse is claimed.

`case-plan.json` maps other-first/ego-first entry, other already inside and opposite-direction left-turn exception context. `yield_sign_control.py` searches Native yield-sign actors and checks the sign trigger volume against the approach waypoint. `crossing_measurements.py` requires source-hashed sign/junction/highway identities, complete vehicle bodies and original-frame mapping, then reports entry order and ego approach/occupancy speed. It leaves official-device exclusion and right-of-way judgments unresolved. Three CPU tests pass in `cpu-tests.log`, exercising trigger selection and rejecting wrong governance or stale frame joins.

Next CPU work: source a real properly erected yield sign and median-opening crossing, construct both vehicles and slow/stop behavior, capture all four source cameras and raw map/device/motion evidence, implement saved finalizer, three physical-risk fallbacks per selected case, semantic proposals and independent audits, then run exact offline, compatibility, saved-processing and assignment strict proofs. Actual sign visibility, official status, statutory crossing and motion remain physical checks; the listed implementation and CPU proofs are worker-owned.

The pinned CPU preflight passes. No frozen input, runtime or batch file was edited.
