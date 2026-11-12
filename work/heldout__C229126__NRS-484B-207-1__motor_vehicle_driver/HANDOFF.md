# C229126 / NRS-484B-207-1 — partial CPU checkpoint

Exact law: The driver of a vehicle overtaking another vehicle proceeding in the same direction shall pass to the left thereof at a safe distance and shall not again drive to the right side of the highway until safely clear of the overtaken vehicle.

Uncovered branch plan: Construct overtaking a same-direction vehicle; compare left-pass geometry, surface clearance and return-to-right timing. Keep “safe distance” and “safely clear” unresolved, with measured physical sweeps.

Frozen evidence.json lists no accepted recordings for this assignment. The source-backed scope review is in `case-plan.json`; no physical or legal conclusion is asserted.

Next CPU action: define exact cases and controlled comparisons for every branch above, then implement and test construction, source cameras, measurement/finalization, three distinct fallbacks for each selected case, semantic proposals, saved processing and independent audits. Run exact `runtime.py offline` and `runtime.py compatibility` for each construction, then `.venv-cpu/bin/python worker_check.py --assignment heldout__C229126__NRS-484B-207-1__motor_vehicle_driver --complete --require-delivery-ready`. The current missing work is CPU work, not a GPU blocker.

## 2026-11-12 construction and measurement continuation

The pinned CPU preflight now passes. `case-plan.json` identifies four exact cases:
`left_pass_wide`, `left_pass_narrow`, `return_before_clear`, and
`return_after_clear`, each prefixed with the full assignment ID. Two comparisons
hold the same road, actors, approach, cameras and duration fixed while varying
either planned lateral pass offset or return timing. The source observation
mapping now covers all eight frozen terms. No accepted recordings are available
for reuse. The exact law has no numeric safe-distance or safely-clear threshold;
the offsets in `overtake_controller.py` are engineering targets only.

`overtake_sequence.py` measures an original 20 Hz source from approach behind,
through a same-direction abreast pass, full-body clearance and rightward return.
It reports minimum left body gap, body clearance at first return and an
observational time gap using the overtaken vehicle's original speed. It rejects
missing original corners, unstable identities, wrong heading, broken frame joins
and incomplete manoeuvres. `overtake_controller.py` selects distinct mapped
lanes and return phases for the four planned cases. Five CPU tests pass with
source-shaped footprints and controlled target changes. Run:

`.venv-cpu/bin/python -m unittest discover -s work/heldout__C229126__NRS-484B-207-1__motor_vehicle_driver/tests -v`

The retained `cpu-tests.log` hash is bound in `result.json`. This is a **partial**
checkpoint. Next, build the exact Native route, actor spawning and four named
synchronized camera acquisition; connect these measurements to a source-bound
finalizer. Complete one primary case's offline, positive/negative compatibility
and saved-only proof before expanding all four cases and their three distinct
risk-triggered fallbacks. Then implement semantic proposals, physical/lifecycle
fixtures, independent delivery and comparison audits, rerun the scoped strict
gate and complete batch strict gate. Actual motion, visibility and legal findings
remain unverified; missing software work is not a GPU dependency.

The same-law C110161 source-backed route selection and bounded steering control
were adapted into this assignment's `overtake_route.py`. Three additional CPU
tests exercise a connected left passing lane in both approach directions,
reject an opposing lane, and verify body-clearance-dependent target selection.
The current `cpu-tests.log` binds **eight** passing tests. Native actor spawning
and synchronized source capture are still pending.

The measurement now additionally requires original lane membership from the
same-lane approach through a measured return to the overtaken vehicle's right
lane. A ninth CPU test rejects a trace that merely moves rightward but never
returns to that lane. `result.json` binds the current nine-test log hash.

The latest scoped checkpoint command, `.venv-cpu/bin/python worker_check.py
--assignment heldout__C229126__NRS-484B-207-1__motor_vehicle_driver --complete`,
exits 0. The complete strict command,
`.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`,
exits 1 at `preparation.py:276` with `Preparation acceptance failed:
partial/missing packages remain`. The return tree has 10,192 files under the
frozen 10,200 cap. Across the 51 assigned packages, 35 are ready and 16 remain
partial. Continue the concrete CPU work above; the strict rejection is a
truthful package-readiness result, not an external dependency.
