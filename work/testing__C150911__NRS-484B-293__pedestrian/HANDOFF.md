# testing__C150911__NRS-484B-293__pedestrian

Status: partial CPU construction and source audit; no delivery readiness claim.

Exact source: NRS 484B.293, “Pedestrians shall move whenever practicable upon the right half of crosswalks.” Frozen assignment and witness index 393 select a pedestrian crossing a one-way road at C150911. The frozen accepted-evidence inventory has zero recordings. The witness is conditional and requires actual crosswalk qualification, access, signals, direction, available passage space, obstacles and participants. The crosswalk must be independently qualified by Native readback. No judgment range or statutory numeric boundary is supplied; practicability remains unresolved without a legal cutoff.

## Coverage and construction

`case-plan.json` now defines five exact cases: `forward_right`, `forward_left`, `reverse_right`, `reverse_left`, and `forward_right_obstructed`, each prefixed by this assignment ID. It defines four controlled comparisons: `forward_half`, `reverse_half`, `directional_right`, and `right_half_obstruction`. The obstruction changes available right-half passage context, not a legal result. Opposing passage directions swap the geometric right half. No baseline recording or existing-evidence reuse is claimed.

`crosswalk_delivery.py` validates required map/crosswalk/access/signal/obstacle/participant source bindings, Native crosswalk qualification and pedestrian access, computes waypoints for either direction and half, calls a lazy pedestrian spawn/route adapter, and cleans up a failed route. Its original-frame measurement requires consecutive 20 Hz frames and synchronized obstacle/participant streams, records crossing station, direction-relative right lateral position, crosswalk occupancy, available right width and participants, and leaves practicability unresolved. Its comparison audit checks fixed source identities and full original frame continuity. `proposals/cases.json` is a draft coverage proposal, not a complete semantic delivery set.

`delivery_audit.py` independently rejects missing/stale Native result, frame map, four camera sources, incomplete original trace, missing obstacle/participant joins, absent passage, unsafe source paths, and an unsupported legal verdict. Its synthetic tests establish software behavior only; they do not prove readable pixels or physical motion. Physical risk for each exact case is recorded in the plan: Native pedestrian spawn/path tracking and four-view visibility may fail. No fallback is authored without a measured site-specific trigger.

## Proof and next CPU work

Run `.venv-cpu/bin/python -m unittest discover -s work/testing__C150911__NRS-484B-293__pedestrian/tests -v`; the passing output and SHA256 are in `cpu-tests.log` and `result.json`. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C150911__NRS-484B-293__pedestrian --complete` for the static checkpoint, then the same command with `--require-delivery-ready` for the strict gate. The latter must remain failing while status is partial.

Next: bind `validate_site` to actual Native crosswalk/map and signal readback, obtain source-hashed crosswalk candidates and obstacle geometry, author exact case configs/construction/manifest and canonical semantic proposals, then run every exact offline and source-bound positive/negative compatibility check. Implement a saved-only process-saved fixture with all four decoded views and compare audits bound to sealed original packets. Reread the law and contracts before strict promotion. Actual CARLA passage, realized obstacles/participants and pixel visibility are later physical checks, not a substitute for the missing CPU package.
