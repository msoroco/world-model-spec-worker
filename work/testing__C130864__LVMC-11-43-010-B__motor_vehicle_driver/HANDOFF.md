# testing__C130864__LVMC-11-43-010-B__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.43.010(B) — The following regulations pertain to the operation of vehicles within a roundabout: The operator of a vehicle entering a roundabout shall yield the right-of-way to vehicles already in the roundabout and wait for a gap in traffic before entering.
Assigned branch(es): Multilane roundabout entry with an already-present vehicle..
Cell: C130864 (multilane_roundabout, enter_roundabout, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C130864__LVMC-11-43-010-B__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-24 exact-case and source-bound roundabout checkpoint

The exact ordinance requires an entering operator to yield to vehicles already in the roundabout and wait for a traffic gap before entering. The frozen multilane witness is accept_conditional and requires the actual entry lane, connected circulating lane, opponent lane/route, possible conflict and jurisdiction. `case-plan.json` now holds six exact targets: connected/adjacent opponent lane wait and enter, plus connected lane wider-requested-gap wait and enter. Five comparisons isolate entry behavior, opponent lane relation and requested initial gap. No numeric gap is a legal threshold. No accepted recording is listed in frozen evidence.

`roundabout_measurements.py` validates source-hashed original map/trace/receipt bytes. It requires two inventoried circulating lanes, a connected ego entry lane, actual opponent route and inside-ring initial point, jurisdiction and conflict-region source references, ring and conflict polygons, original eight-vertex vehicle bodies, and ordered 20 Hz frame/time/speed histories. It measures first sampled ego ring entry, circulating/opponent conflict occupancy at that frame, pre-entry stopped frames and body separation. It leaves right-of-way and gap judgment unresolved; synthetic fixtures cannot prove real map geometry or camera visibility.

Eight focused CPU tests passed in `cpu-roundabout-tests.log`, including CLI replay and rejection of unconnected lane, opponent outside ring, absent conflict source, changed bytes, dropped frames, missing original body and diagnostic provenance. Static scoped check passed in `assignment-check.log`. Exact scoped strict check failed on truthful partial status in `strict-gate.log`. Current passing proof hashes are in `result.json`. Next CPU work: bind a reviewed real Native roundabout packet and six executable scene/controller bundles, synchronize and audit four cameras, author finalizers/proposals, run exact offline/positive-negative compatibility and saved-delivery/comparison proofs. Physical motion, realized traffic gaps and pixel visibility await later local verification.

## 2026-11-23 lazy Native construction checkpoint

Added `native_roundabout.py` SHA256 `ca7dbc4883d698ec218cd97e1f8fbbea6ac970429e46160aab9bcd8fe9d94cfa`. It hash-checks an exact-case construction packet, reuses the source-backed multilane map audit, checks an ego entry route connected to its circulating lane and an opponent route in the actual circulating lane, validates finite/connected route samples and source-selected blueprints/spawns, then lazily spawns two distinct CARLA actors with first-actor cleanup if the second fails. `TimedRoute` holds until a specified engineering release tick, then applies bounded steering/throttle requests along the source route and rejects tracking loss. The requested release tick does not establish an actual safe traffic gap or legal yielding; the saved original trace and pixel review must do that.

`tests/test_native_roundabout.py` SHA256 `0fb3eeb7cbf61d68608ad0831dd373039e3928ca8c79cb4f05611df6739f7a3b` exercises source-bound construction, distinct spawns, hold/release, wrong lane, stale source, disconnected route and tracking loss. The full focused suite passes 12 tests: `cpu-roundabout-tests.log` SHA256 `73f2a2170625c27e84db9752426f44554050dbd20dd37ecadcb6d3e2ed475e45`. Pinned preflight exits 0: `cpu-preflight.log` SHA256 `ea685bfbcdb1b0bde932b595d92311cbe7ba9a1af052b2de1292092fe00a86f1`. Scoped static exits 0: `assignment-check.log` SHA256 `050c89d4e0371aba3770d30ebfc24be48749844dfadf62f72ade89c13d41ff0f`. Exact scoped strict exits 1 on truthful partial: `strict-gate.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

Next CPU work: bind reviewed fixed-cell roundabout map and lane/route source packets to all six exact cases; provide a complete 20 Hz world/camera runner and finalizer, semantic proposals, source-specific diagnostics and positive/negative compatibility, saved-only processing and independent delivery/comparison audits. Later physical work checks realized motion, whether the circulating opponent was present and conflicted at ego entry, camera visibility and actual traffic gap. No legal gap threshold is invented.

## 2026-11-24 original trace capture checkpoint

Added `capture_roundabout.py` to join two distinct original actors and source-checked roundabout construction to 900 contiguous synchronous 20 Hz world frames. It retains eight world-space body vertices and measured speeds for each actor, writes a SHA-sealed trace and source receipt only after completion, and brakes both actors on capture failure. Short fixture captures are explicitly diagnostic and cannot pass `roundabout_measurements.measure`. One 900-frame CPU fixture successfully joins the saved measurement; timing, missing-body and world-rate negatives are tested. This is an executable capture boundary, not proof of a real Native map or legal traffic gap.

Pinned suite passes 17 tests; preflight and scoped static pass. Exact scoped strict exits 1 on truthful partial. New SHA256 receipts:
- `cpu-original-capture-tests.log`: `d33dd64f1befd0f3707f3a3c6d7cfef93651550d76bc0292a2886eda29bf557d`
- `cpu-original-capture-preflight.log`: `72ea09a845c1a231de4ed06a6481c273b6e6899223540974b87b9e385c03d0fb`
- `cpu-original-capture-static.log`: `050c89d4e0371aba3770d30ebfc24be48749844dfadf62f72ade89c13d41ff0f`
- `cpu-original-capture-strict.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`

Next CPU work: reviewed map and route packets for all six exact cases, full world/sensor lifecycle runner with four-camera capture, saved camera decode and finalizer, semantic proposals, offline/positive-negative compatibility, and independent delivery/comparison audits.
