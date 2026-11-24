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

## 2026-11-24 pedestrian source identity checkpoint

The original crossing measurement now requires one stable pedestrian actor ID and pedestrian source on every frame. The saved independent audit rechecks that identity and source against its fixed source map. Nonintegral frame identities and resealed mid-crossing actor swaps are rejected. This prevents a crossing trace assembled from different walkers; it does not establish physical practicability.

### Receipts

- `cpu-pedestrian-identity-tests.log` exit 0, SHA256 `6cd71823324e00f3e492b736b754e1c27d420b274e3dbbeaa361f37aa3c45304`
- `cpu-pedestrian-identity-preflight.log` exit 0, SHA256 `8a59848d4925164aaa8e12a1e90951e3a29e30e65d169db1ea89ebb9838b5801`
- `cpu-pedestrian-identity-static.log` exit 0, SHA256 `469b38a88e374ec61f43f64cc664c17929eff2d805883f0e97c4ecf85ca00e62`
- `cpu-pedestrian-identity-strict.log` exit 1, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`
- `crosswalk_delivery.py` SHA256 `ed437f71256b04059c787c2befe50ec02d828a97d8358a4d87413e96585ae532`
- `delivery_audit.py` SHA256 `b3e66d727849cb9aa74ad5c474deec8d9aaa338e9841fce42faeb6f50bebeba0`
- `tests/test_crosswalk_delivery.py` SHA256 `12626dde787380b6914af406b1a3c609f8e181e91b85f17200cd358746bd5556`
- `tests/test_delivery_audit.py` SHA256 `86cecf9f9647f0985a9df8fe9cdf9af41b06585548ab621cfa7c1d7b9e160080`

Ten focused tests, pinned preflight and scoped complete static check pass. Exact scoped strict exits 1 because status remains partial. Next CPU work: Native site acquisition, all selected-case bundles/diagnostics, positive and negative compatibility, semantic proposals and full decoded delivery audits.
