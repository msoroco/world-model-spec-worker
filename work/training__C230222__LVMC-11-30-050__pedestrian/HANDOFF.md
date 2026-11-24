# training__C230222__LVMC-11-30-050__pedestrian

Status: partial. The frozen law allows a route at right angles to the curb **or** the shortest route to the opposite curb; a crosswalk is an exception. The 0 accepted membership rows supply no reusable original. No legal or physical outcome is claimed.

## New CPU construction and proof

- `native/route_meter.py` measures original entry/exit positions, distance to the two authored curb segments, full route length, nearest-point shortest distance, right-angle deviation, and crosswalk polygon occupancy. It retains source hashes and assigns no legal verdict. Its 600-frame/20 Hz CPU fixture checks a perpendicular shortest route, longer diagonal, skewed shortest diagonal, and crosswalk case, and rejects a missing source position and duplicate Native frame. `native/route-meter-proof.json` SHA-256 `bb34c090c23c4bd151e859420f80b5414f681779ef62b866d273d9fa189fc37c`.
- Two exact, **unselected** 30-second/20 Hz four-camera Native bundles are bound in `draft-route-manifest.json` SHA-256 `4337c064d551d3c167dfcb82e28edbda3078b1de6a668c3825296352b33ff0d5`. Condition A holds a right-angle path; condition B requests a longer diagonal. Both use the same authored road, pedestrian controller, camera geometry and source schema. The Native runner retains original trace positions, frame/time joins, four source RGB hashes and lossless camera video; execution requires an owned CARLA world and is untested here. Condition A construction SHA-256 `18d990180d0bb06729d67752155961f9990d790403a816dd20c675130da11528`; condition B `3a57d54d7f331e6ea74b47e25303cbb40de9efc2e23e9d66e91d7d267872be01`.
- Pinned CPU `runtime.py offline` passed for both exact unselected bundles. Returned logs: condition A SHA-256 `aa0b9fa272d10371ed477493d2a9a3d13a71ef446acf1941743deb681bd997d0`; condition B SHA-256 `243d1a1be5bd43e21ec034c90bd7e8fc35cf6279ab659d7d42caa0a9da99c894`. The runtime preflight also passed.

## Precise remaining work

Promote only after independent source review of authored road/crosswalk geometry, actual Native path and camera pixels. Implement selected-case manifest, three distinct risk-based fallbacks per selected case, exact positive and negative compatibility receipts, saved processing from original source and four videos, and independent acceptance and comparison audits. The source meter's engineering numbers require reviewer judgment; they are not legal cutoffs. Physical CARLA execution and canonical acceptance remain local-operator work.
