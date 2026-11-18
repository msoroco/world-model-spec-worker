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

After the 18-test checkpoint, the complete strict command
`.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`
was rerun and exited 1 at `runtime/scenario_pipeline/worker_exchange/preparation.py:276`
with `ValueError: Preparation acceptance failed: partial/missing packages remain`.
The updated environment preflight and this assignment's scoped nonstrict gate
pass. C229126 remains a truthful partial CPU construction, and 16 of the 51
batch assignments remain partial. Resume with the exact first-case bundle and
proof work listed above, then rerun scoped strict and the complete strict gate.

## 2026-11-12 first exact bundle and source-bound proofs

`left_pass_wide` now has a C229126-specific `config.json`, inline `construction.json`, frozen `delivery-construction-manifest.json`, `measurement-contract.json`, and source-hashed `diagnostic-recipe.json`. The construction bundles the CARLA-lazy runner, same-direction scene and controller, original body/lane/speed recorder, four named camera streams, finalizer and 18 CPU tests. The 1.5 m planned left gap and 1.0 m return threshold are engineering targets, not statutory cutoffs.

Exact primary construction SHA-256: `e4e2477231e45d564034103eded1a8f0dd48661207967d2adf5910423b2b98cb`. `first-primary-proof.json` SHA-256: `b26b87113743c406bd7d993adb34d52e6acd0af0589aa59dd1c944416033a9c2`. That compact UTF-8 proof retains the exact offline test log, positive compatibility receipt and analysis log, deleted-`participant_footprints.jsonl` negative log, and saved-only processing receipt/log with their SHA-256 values. It is compacted into one returned file to stay within the frozen 10,200-file cap; generated diagnostic media remain under `.runtime-work/`.

The current exact commands are the `offline.command`, `compatibility.command` and `saved_processing.command` entries in `first-primary-proof.json`; all exited 0. Compatibility passed Native validation, Lean decoding, full video decode and four-camera checks. Saved processing reported `passed=true`, `originals_preserved=true`, `missing_evidence=false`. This synthetic CPU fixture does not show actual safe distance, clearance, visibility or legal acceptance.

The scoped nonstrict `worker_check.py --assignment heldout__C229126__NRS-484B-207-1__motor_vehicle_driver --complete` passes. Remain **partial**: complete the other three exact cases, three risk-triggered fallback constructions per selected case, independent delivery and comparison audits, canonical semantic proposals, all exact-case saved proofs and the scoped strict gate. Rebind this first case if its construction, fixture, contract or runtime hash changes.

Final turn checks: updated `.venv-cpu/bin/python runtime.py preflight` passes; C229126 scoped nonstrict gate passes; its scoped strict gate exits 1 at `preparation.py:276` because this package remains partial. The complete `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` rerun exits 1 at the same acceptance check: 35 ready and 16 partial assigned packages. `work/` has 10200/10,200 returned files. The next CPU step is to compact return proofs without losing their hash-bound contents, then construct and prove `left_pass_narrow` using this first case as the template; continue the return-order cases, fallbacks, semantic stages and independent audits.

## 2026-11-15 left-pass narrow exact offline checkpoint

`cases/left_pass_narrow/construction.json` binds the second exact C229126 case to the same 20 Hz, 320-frame four-camera contract and a 0.5 m planned left-gap target, while the wide case retains 1.5 m. These are engineering controls, not legal cutoffs. Its construction SHA-256 is `6e3927e2c24bbdb0ca85a89bb9cde36844754c6fa2a0542db3eb43e9d5cb95a6`; `cases/left_pass_narrow/measurement-contract.json` names the same retained original source requirements. `delivery-construction-manifest.json` selects this exact construction without changing the proved wide construction.

Exact offline command: `.venv-cpu/bin/python runtime.py offline --manifest work/heldout__C229126__NRS-484B-207-1__motor_vehicle_driver/delivery-construction-manifest.json --case heldout__C229126__NRS-484B-207-1__motor_vehicle_driver__left_pass_narrow --output .runtime-work/c229126-narrow-offline-v2 --python /scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-held/.venv-cpu/bin/python`. Exit 0, 18 tests passed; `left-pass-narrow-offline.log` SHA-256 `a8fec39f338892bc828cd9939da776296a10058f726b186db4e3aa7ecf79a476`. The first command with a relative `--python .venv-cpu/bin/python` failed because the runtime executes from the materialized output directory; the passing command uses the absolute CPU interpreter. Scoped nonstrict `worker_check.py --assignment heldout__C229126__NRS-484B-207-1__motor_vehicle_driver --complete` exits 0.

Status remains **partial**. The next CPU action is a narrow-case source-shaped diagnostic, positive/missing-original-source compatibility and saved-only processing with distinct measured gap; then build both return-order cases and all three risk-triggered fallbacks per selected case, semantic proposals and independent audits. Rerun the exact proofs and scoped strict gate. No physical or legal acceptance is claimed.

## 2026-11-15 four-primary and twelve-fallback CPU proof checkpoint

The pinned CPU preflight passes with Lean/Lake 4.28.0 and FFmpeg/FFprobe; `worker_check.py --updates` reports version 0 and no pause. The repository six tests and this assignment's 18 tests pass. The scoped nonstrict `worker_check.py --assignment heldout__C229126__NRS-484B-207-1__motor_vehicle_driver --complete` exits 0.

`delivery-construction-manifest.json` now lists all four exact planned cases and three physically distinct fallbacks for each. Candidate 1 reduces steering gain for overshoot/oscillation risk, candidate 2 reduces ego target speed for pass-closure risk, and candidate 3 raises the overview mount for body-visibility risk. The same controller fallbacks are available to every linked case. All 12 candidates pass exact `runtime.py offline --candidate fallbackN` and positive/missing-original-source `runtime.py compatibility --candidate fallbackN`; the source-hashed commands, receipts and negative logs are packed in `first-primary-proof.json` (SHA-256 `cfafa40739b1f7b6ad76e06671f1177af2fa94e7cb7e9cbdac70b356189f394c`). The packed proof is a checkpoint: the strict ready gate requires separate bound receipt/log files in each manifest candidate.

All four primaries pass exact offline, positive/missing-original-footprint compatibility, four-camera decode and saved-only `runtime.py process-saved`. The synthetic diagnostics measure a 2.0 m versus 0.5 m abreast gap and first rightward returns at frame 38037 with -2.0 m full-body clearance versus frame 38040 with +7.0 m. These are fixture observations, not realized Native evidence or legal cutoffs. `comparison_audit.py` independently checks fixed map, trace, cameras, actors, timing and longitudinal geometry, rejects missing bodies/changed fixed road or control, and accepts both intended differences. `delivery_audit.py` independently joins original frames, trace and both participant bodies, fully decodes four original source cameras, and rejects missing body/camera sources for all four cases. Its receipts explicitly leave actual pixel visibility and physical completion false. Exact selftest commands and hashes are in `first-primary-proof.json`.

Status remains **partial**. Next worker-owned CPU steps: (1) proof-preserving return compaction and separate fallback receipt/offline/analysis/negative files, then bind them in each manifest candidate; (2) per-case post_capture and delivery_acceptance commands, negative receipts and physical lifecycle tests; (3) canonical semantic stage proposals and `proposals/semantic-index.json`; (4) shared branch review, ordered GPU queue and local integration proof; (5) rerun every affected exact compatibility/saved/comparison proof and the scoped/full strict gates. Actual Native motion, pixels and legal judgments remain unverified after CPU preparation.

### 2026-11-15 exact CPU delivery preparation passed

The four exact C229126 primary cases and all twelve distinct fallbacks now pass the pinned offline and positive/missing-original-source compatibility commands against the current source-hashed constructions. The canonical seven-stage semantic proposal validates for all four selected cases. The case plan maps mandatory observations to the two actually captured streams and includes the exact four-view 16 s camera plan. All sixteen bundles embed that current plan. Source delivery and controlled comparison audits pass their positive and negative CPU fixtures. Each case also has three synthetic physical-outcome fixtures, ordered capture closure through saved processing, and a positive/stale-source negative acceptance fixture. Synthetic sources do not establish actual Native motion, pixel visibility or a legal judgment.

The 18-test assignment suite passes. `.venv-cpu/bin/python worker_check.py --assignment heldout__C229126__NRS-484B-207-1__motor_vehicle_driver --complete --require-delivery-ready` exits **0** with `static_checks_passed: true`. `result.json` is **ready** with `readiness_kind: delivery_prepared`. Continue the other incomplete batch assignments and shared batch queue/review work; this scoped pass is not a full-batch delivery acceptance.

## 2026-11-18 current-runtime source conflict

Current-runtime compatibility is blocked by conflicting diagnostic measurements for the same actor. In frame 38033, `capture/evidence.jsonl` gives ego actor 205 position `[98, 5]` and a matching moving body. Its `original_observations.participants` packet, repeated in the graph `observed_evidence`, gives actor 205 position near `[100, 1.75]` and a body centered there. The evidence ego advances from x=98 to x=122 over nine frames while the observation packet remains near x=100. `traffic_spec_adapter.attach_original_participants` correctly rejects this as `Participant graph/telemetry geometry mismatch: position`. The diagnostic is explicitly synthetic, and these two tracks cannot both describe its same-frame actor. Regenerate a source-coherent synthetic observation packet and graph from the case trajectory, then rebind the recipe source SHA and rerun current-runtime exact offline, positive and missing-source compatibility, and clean saved processing for all cases and candidates. Reconstruct the missing synthetic physical proof script and rerun its lifecycle checks. Keep `result.json` partial until those exact proofs and the scoped strict gate pass.
