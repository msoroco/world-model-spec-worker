# testing__C262661__NRS-484B-363-1__bus_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.363(1); with 484B.363(9) — A person shall not drive a motor vehicle at a speed in excess of 15 miles per hour in an area designated as a school zone except: (a) On a day on which school is not in session; (b) During the period from a half hour after school is no longer in operation to a half hour before school is next in operation; (c) If the zone is designated by an operational speed limit beacon, during the hours when the pupils of the school are in class and the yellow lights of the speed limit beacon are not flashing in the manner which indicates that the speed limit is in effect; or (d) If the zone is not designated by an operational speed limit beacon, during the times when the sign designating the school zone indicates that the speed limit is not in effect. As used in this section, “speed limit beacon” means a device which is used in conjunction with a sign and equipped with two or more yellow lights that flash alternately to indicate when the speed limit in a school zone or school crossing zone is in effect.
Assigned branch(es): Motor bus in a school zone with children.
Cell: C262661 (school_zone, travel, children); actor: bus_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C262661__NRS-484B-363-1__bus_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 school-zone bus speed and exception checkpoint

`case-plan.json` now has fifteen exact unexecuted cases and twelve comparisons. The 14.9/15.0/15.1 mph targets probe the express speed boundary. Other controls isolate no-session day, the half-hour after operation and before next operation, class hours with operational beacon flashing/not flashing, nonbeacon sign active/inactive, one-light and nonalternating-light beacon definition probes, zone boundary, children presence and bus versus other motor vehicle. Children alone do not resolve a temporal exception.

`school_zone_observations.py` accepts only a hash-sealed original Native context and 20 Hz trace. It requires source references for the designated zone, property, bus route/driver, children, civil date/time, calendar, operation and class hours, beacon designation/operability/lamp configuration/history and sign periods. It retains per-frame bus speed in m/s and mph, inside-zone state, each yellow lamp state, sign indication and children inventory. Independent session and beacon-designation facts remain separate. It does not declare the limit applicable or a violation from speed alone; all exception and beacon-definition judgments remain unresolved. Diagnostic fixtures are rejected as delivery evidence.

Pinned preflight passed (`cpu-preflight.log`, SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`). Seven focused tests passed (`cpu-school-tests.log`, SHA256 `c9a6d8f3060916129de4809fbbaa000a2a56ea91ce55c6170e0a3aa067e42b6d`). Scoped static check passed (`assignment-check.log`, SHA256 `5a8a41eecd92d272be71cb394065baa5466c89b04d79dc3bc55f408fe79e2edb`). Exact scoped strict exited 1 on truthful partial status (`strict-gate.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`). Source hashes: plan `dcd754e2ca3cc7515bfbcfbc49009bf46504e777d85ee27bd7432c88bf538b28`, measurement `c3eba4a4bdfa0c686b43760b377f322b1083d294fc40b3ac37b505e8a65a5b10`, focused tests `cec32588a9eecf29879391984189b1aabe0bbc622d2ce4ae940a051b6aec4e75`.

Remaining CPU work: bind a reviewed Native designated school-zone map, bus route, children and independent school-calendar/device source, construct fifteen physical scenes/controllers with synchronized original four-camera capture, validate the operational alternating-yellow beacon and sign-time branches, then implement finalizers/proposals, exact offline and positive/negative compatibility, saved-only delivery and twelve comparison audits. Physical and legal acceptance remain unverified.
