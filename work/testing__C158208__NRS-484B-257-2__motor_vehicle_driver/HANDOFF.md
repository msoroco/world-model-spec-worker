# C158208 CPU handoff — NRS 484B.257(2)

Status: **partial**. The fixed cell is a one-way-to-two-way intersection with a yield sign. Subsection 2 requires the signed-entrance response in the manner prescribed by subsection 1 and continued caution/yield to vehicles not obligated to stop or yield that are inside or immediately approaching, except during actual officer or signal control. The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

`case-plan.json` maps other already inside, approaching, separately obligated, no-slow response and officer exception context. `yield_sign_control.py` checks an actual Native sign trigger against the ego approach. `yield_entry_measurements.py` joins original frames to pre-entry ego speed/reference position, complete ego and other bodies, non-through-highway status and an all-entrance device inventory. It reports observed slowing and other occupancy/obligation without judging immediate hazard or caution. Three CPU tests pass in `cpu-tests.log`, including Native trigger selection, another entrance's stop obligation, active-signal exclusion and stale-frame rejection.

Next CPU work: construct/source the subsection-1 stop-line/crosswalk/nearest-view hierarchy, proper yield sign and all entrance devices; build connected ego/other routes and approaching timing sweep; capture all four raw cameras and original body/sign/road sources. Implement saved finalizer and measurement contract, three distinct physical-risk fallbacks per selected case, semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Physical sign, status, motion, sight and visibility remain later source/CARLA checks; the listed implementation and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C158208__NRS-484B-257-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C158208__NRS-484B-257-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C179789__NRS-484B-600-1a__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.

## 2026-11-24 subsection-1 reference implementation

`yield_reference.py` now binds the signed-entrance review to the exact context SHA-256, yield actor ID and all four original camera hashes. It selects the ordered subsection-1 response reference: marked stop line, else near crosswalk, else finite nearest-view point. It preserves proper-sign, safe-speed and nearest-view judgments as unresolved. `yield_entry_measurements.py` now requires this source review and returns the selected reference with its source hash. Four focused tests pass in `cpu-tests.log`, including ordered fallback, missing nearest-view source and changed-camera rejection. The assignment-scoped complete nonready check passed in `.runtime-work/c158208-scoped-reference.log`. Status remains **partial**. Next worker-owned work: Native runner and synchronized four-camera capture, exact case constructions and risk-based fallback, saved finalizer, semantic stages and all CPU delivery proofs. Synthetic test camera bytes are only hash-binding fixtures, not decoded physical evidence.

The ordered-reference test also rejects an intersection context changed after site review. Four focused tests and the scoped complete nonready check passed again in `.runtime-work/c158208-scoped-reference-v2.log`.

## 2026-11-24 Native source and site checkpoint

The package now owns `native-map-plan/signed-intersection.xodr` and `yield_site.py`. The authored-site validator checks the one-way signed ego road, two-way cross street, exact junction lane links and single lane-governing yield signal; `validate_native_site` rejects a different loaded road/lane/junction or yield trigger. It does not infer legal through-highway status or a proper sign from the XML. `yield_capture.py` writes complete Native ego/other body footprints, observed ego speed, reviewed reference-boundary position and exact four-camera callback joins, only from a current monotone Native tick. `bind_site_review` binds human/source-camera findings to the context hash, all original camera hashes and reviewed frame IDs. The saved `yield_entry_measurements.py` and `yield_reference.py` now require those frame joins and full review coverage. Synthetic camera files in tests are hash/join fixtures, not decoded physical footage.

Nine focused CPU tests pass in `cpu-tests.log`; the assignment-scoped complete nonready check passed. Status remains **partial**. Next worker-owned steps are the Native runner and real four-camera encoding, source-reviewed non-through-highway and all-entrance device context, five exact case stages including actual officer-control source, selected fallbacks, saved finalizer, semantic proposals, offline/compatibility/saved-processing and physical fixture proofs, and independent delivery/comparison audits. Do not mark ready before the exact scoped strict gate passes.

The `yield_other_obligated` comparison now has its own authored `native-map-plan/other-stop-intersection.xodr`, with a stop signal on the south other entrance. `yield_site.py` checks its lane validity and requires a distinct Native stop trigger there. `yield_stage.py` defines the five exact case identities, other-vehicle inside versus approaching start/release, the no-slow ego target, and the explicit officer-source requirement. These are construction targets, not observed motion or legal cutoffs. `yield_entry_measurements.py` now rejects an incomplete three-entrance device inventory; the officer-exception case requires an original-camera/context-bound `officer_review.json` showing control at entry, while authority remains unresolved. Fourteen focused tests pass. Native staging/runner and encoded capture remain to be implemented; no physical sign, officer or vehicle behavior is claimed.
