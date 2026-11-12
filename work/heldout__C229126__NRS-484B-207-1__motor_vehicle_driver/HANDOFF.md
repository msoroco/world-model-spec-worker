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

## 2026-11-12 Native source and actor construction checkpoint

`native_scene.py` now selects a connected same-direction left-passing lane pair,
spawns the overtaken actor ahead of the subject in the right lane, and destroys
the first actor if the second spawn fails. CPU fakes exercise creation and
cleanup in both approach directions. `overtake_source_capture.py` retains
original four-corner bodies, mapped lanes, same-road tangent, actor headings,
overtaken speed and joined 20 Hz frame/time rows. Its tests reject a cross-road
pair and a broken frame join. `overtake_route.case_target` connects the four
exact case settings to source-measured body clearance, distinct lateral pass
targets, and signed early/late right-return thresholds. These settings do not
define statutory safe distance or safely clear.

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C229126__NRS-484B-207-1__motor_vehicle_driver/tests -v`; all 14 tests pass. The
current `cpu-tests.log` SHA256 is `77e6c40eebf4cff184dfa1d9e9c11b6afae7bee201a1b04e0c61e9700ca02645`. Run the scoped nonstrict gate
with `.venv-cpu/bin/python worker_check.py --assignment heldout__C229126__NRS-484B-207-1__motor_vehicle_driver --complete`. Next CPU construction
is a CARLA-lazy runner wiring this scene, controller and source recorder to four
named synchronized cameras, Native frame map and pipeline trace. Then complete
one exact case finalizer, offline/positive-negative compatibility and saved-only
proof before expanding the other cases and their three fallbacks each. The
package remains partial; these CPU fakes establish no actual motion, visibility,
statutory safety or local acceptance.

The updated CPU preflight passed with pinned numpy, FFmpeg/ffprobe and Lean/lake
4.28.0; the root six CPU tests passed. The C229126 scoped nonstrict gate passed
after this checkpoint. The full strict command
`.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`
exited 1 at `runtime/scenario_pipeline/worker_exchange/preparation.py:276` with
`Preparation acceptance failed: partial/missing packages remain`. This tree has
10191 returned work files against the frozen 10,200 cap. Exactly
35 of 51 batch assignments report ready and
16 report partial. The full gate did
not claim delivery readiness; continue the runner and proof construction above.

### Four-camera Native runner wiring

`runner.py` now wires the selected scene, measured lateral/signed-return
control, original body/lane/speed recorder, pinned `PipelineCapture`, Native
`FrameMap`, four synchronized FFV1 RGB streams and cleanup/readback into a
CARLA-lazy prospective 320-frame runner. `overtake_camera.py` implements the
four named source cameras at 20 Hz. CPU tests check exact case/controls/camera
configuration and original full-body abreast detection. All 16 tests pass;
`cpu-tests.log` SHA256 is `ffe4ade2b8c49ce6f349267c5accb76be638b4dffafe22ad4c277d6ebe18472e`. This runner has not been launched against
CARLA. Exact config/construction bundles and a source-bound finalizer are the
next CPU items; only then can offline, compatibility, saved-only and fallback
proofs be run. The result remains partial.

`overtake_finalizer.py` now performs saved-only original frame/trace/body joins,
measures the pass and return sequence, writes derived measurement channels from
the original body source, and leaves physical and legal conclusions unconfirmed.
The new positive CPU test exercises analysis and result construction; deleting
the original body source causes the required negative rejection. All 17 tests
pass with `cpu-tests.log` SHA256 `155511f79f0e90a1079cecce54516833ded5e16f776c053810638d645632764a`. The exact next step is to create one
source-hashed `left_pass_wide` config/construction/measurement contract and
diagnostic recipe, run its exact offline, positive/negative compatibility and
saved-only proof, then expand the other planned cases and fallbacks.

The four-camera creation test verifies four sensor spawn/listen calls, joined
frames and rejection of a missing source frame. The source-shaped finalizer
result also passes pinned `worker_exchange.native_output.validate_result`.
All 18 tests pass; current `cpu-tests.log` SHA256 `8f609695c5cb417a48a7a9218da0b60a95365a72ac6e96a16a480793c58605a3`.
