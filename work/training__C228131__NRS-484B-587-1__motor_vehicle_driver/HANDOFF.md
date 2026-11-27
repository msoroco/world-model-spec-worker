# NRS-484B-587-1 at C228131

## 2026-11-23 controlled-entry CPU continuation

The exact text prohibits driving a vehicle **onto or from** a controlled-access
highway, when official devices giving notice are erected, except at the
indicated entrances and exits. The existing selected witness and comparison
cover entry only. An exit branch and its comparison still need explicit
source-grounded planning; an entry diagnostic cannot discharge that alternative.
The frozen membership snapshot contains no accepted recording for this scope.

`entry_cpu.py` constructs two 600-frame, 20 Hz, 30-second authored entry
requests with the same highway edge and indicated gate at x=0 m. The controlled
target is a requested footprint crossing at x=0 m or x=60 m. It encodes four
distinct FFV1 synthetic color streams per request, byte-hashes each stream and
binds all 4,800 camera frame joins to the track. Two positives and two altered
source negatives passed: a fourth-camera frame join, and a changed route with
the source hash rebound. `entry-cpu-proof.json` SHA-256
`a56f9b3c34c09b497cd0f50c012639b589a43fdfb4005ea444df81a6e1e31d0d`.
Independent `audit_entry_cpu.py` rechecked both crossing coordinates, source
hashes, eight complete video decodes and all 4,800 joins.
`entry-cpu-audit.json` SHA-256
`dd4f35be45454f10edad0c17ab0b038ef4b7bd50bc942c877495734117dcfbf9`.
Generated tracks and videos are only in `.runtime-work/c228131-cpu/entry-20261123/`.

`saved_entry.py` recomputes a footprint entry event from retained pose,
frame-map, road and device-context bytes. It requires all four original camera
joins, a hashed road source, designation, authority, erection, device content
and entrance extent. Two 600-frame synthetic positives and seven missing or
altered-source negatives pass via `prove_saved_entry.py`.
`saved-entry-proof.json` SHA-256
`012025390943e7b41a7f71711d12b6782c09ae2eaed53702c58cfdad2855f6d0`.
Synthetic source declarations do not establish official authority or pixels.

`build_cpu_draft.py` binds the two exact cases in current selectable
`draft-entry-manifest.json` SHA-256
`35a48a8430e862e158aa5824872051a2c334f8454557314f808bb2011149f509`.
Both pinned `runtime.py offline` checks passed without simulation; exact logs
under `.runtime-work/c228131-cpu/offline-witness_1/` and
`offline-witness_2/` hash to
`865103f9ed93ce82df47adaa14bdf39673dd6dc998961a20b3ba3e8668125e1f`
and `97d3621a2a7041c97612366d3b0202919dc861300cd6f161fabad7855146372c`.
The bundled runner is explicitly CPU diagnostic only and has no CARLA execution.
Current pinned compatibility stops at missing `measurement_contract`.

Next CPU work: author a connected road and indicated entrance/exit map, real
Native motor-vehicle controller with four source cameras, original saved
capture/finalizer, and both entry and exit comparisons. Add source-bound
measurement contract and fixture recipe, pinned compatibility and saved-only
proofs, tested fallbacks, semantic proposals and independent delivery audits.
No physical controlled-access designation, official-device authority, actual
entry/exit, pixels, legal verdict or membership is claimed. Result stays
`partial`.

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `enter_road` / `traffic_control_device`.

Exact statutory source: NRS 484B.587(1). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Entry with additional controlled-access context.. Planned comparison variable: `controlled_access_entry`. Requests: driver uses an indicated controlled-access entrance; driver joins controlled-access road outside the indicated entrance. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: official traffic-control devices indicate the entrances and exits of a controlled-access highway; the subject drives onto or from the highway.

Timing to retain: the violation is the entry or exit itself, judged at the point where the footprint leaves or joins the highway.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-25 selected entry CPU preparation

The fixed C228131 `enter_road` cell now has two selected exact entry cases: `witness_1` requests crossing near the source-indicated entrance and `witness_2` requests crossing 60 m away. `native/geometry.py` authors a highway, frontage road and paved entrance candidate; `native/route.py` holds the same controller and relative trajectory with the crossing location changed. `native/runner.py` requests 600 frames at 20 Hz, retains original body/trace/frame-map evidence, captures the four canonical cameras, seals its lifecycle, destroys owned actors and restores the world. `native/finalize.py` joins the original entry point and path to separate access and device reviews plus nine hashed authority/context sources. These are software requests and evidence methods. The paved entrance's Native lane connectivity and the generic sign prop's actual indicated content require original local review.

The two primary bundles and their common steering-gain fallbacks passed current pinned `runtime.py offline` and public `runtime.py compatibility`, including removal of `device-authority.txt` as a negative source. Both exact cases passed recorded-only saved processing. The eight canonical semantic stages passed direct current-runtime validation. Both cases passed synthetic physical met/not-met/unverified triads and sealed lifecycle checks. `delivery_audit.py` passed two positive and two missing-source negative checks; `comparison_audit.py` passed the fixed road/device/authority and measured indicated-versus-outside contrast, plus an omitted-case negative. The selected commands and hashes are in `execution-manifest.json`, `case-plan.json`, and `proofs/`. Direct current-runtime execution-manifest, semantic, delivery-handoff and public-receipt validators passed. No original CARLA run or accepted membership exists.

The exact law separately covers driving **from** a controlled-access highway. This assignment's frozen maneuver is `enter_road`; `inputs/coverage/candidate-cells.json` lists only C62472 and C62507 as `exit_road` cells, both with empty `candidate_ego_parties`. No motor-vehicle-driver-eligible frozen exit assignment is supplied. `case-plan.json` retains this alternative as `alternative_pending`, so the full-branch ready gate correctly cannot pass. A new eligible frozen exit binding and selected indicated/outside exit comparison are the exact prerequisite to complete full-law preparation. Keep `result.json` partial; do not treat the entry pair or synthetic authority sources as proof of the exit branch, official status, physical entry, or legal outcome.

## Unselected from-highway exit CPU construction (2026-11-26)

The exact clause says "onto or from." `native/exit_geometry.py` authors a separate outbound paved ramp in the C62507 controlled_access_road / exit_road / traffic_control_device shape. `native/exit_candidate.py` requests a 600-frame, 20 Hz highway-to-frontage route for indicated and outside exit points, then measures the first original vehicle-footprint leave event against a hashed road, independently sourced exit extent, device authority/content/erection and four source-camera joins. It rejects missing or altered source hashes, a camera mismatch, reversed direction and multiple exits. Six package tests passed in `exit-candidate-tests.log` (SHA-256 `7971df6858740157e2613d5575b24e2afa21094d50801109ec8a7bf599f7b815`). The unselected proposal is `exit-candidate-proposal.json` (SHA-256 `f97a35a83f984b32bd03869dd6014ffc51aa1c672bd6e61e325502fab4b81a2a`).

C228131 remains frozen as `enter_road`, so this exit cannot be silently selected in its two entry cases. The unallocated C62507 catalog row has the right exit_road and traffic_control_device shape but `candidate_ego_parties: []`; a motor_vehicle_driver actor binding is not established by that row. The proposal therefore has no execution-manifest entry, semantic selection, compatibility or saved-only receipt, and it makes no Native lane-connectivity, official-authority, physical or legal claim. Lead review of a valid same-role supplemental assignment and its exact selected exit chains is the remaining CPU path. The original two entry cases and their bound receipts were not modified.

## 2026-11-27 source-bound exit candidate continuation

`native/exit_finalize.py` now joins separate access and device reviews to the exact road, pose, frame-map and five authority source hashes before invoking the 600-frame saved exit meter. It requires four named camera source paths and rejects altered exit-extent bytes or a missing device review. Its diagnostic receipt explicitly leaves video decode and original pixels unverified. The two synthetic indicated/outside exit positives and altered-source negatives passed in `exit-candidate-tests.log` (SHA-256 `e2b69a7b2aa9288d391dd212bb85c43b72dd4e4ac53da63f50274a7dcafc50b6`). Finalizer SHA-256: `916518f276236415910f0a23ef6562a8963cdd8b4c8c0118f9b3fa94910137c0`. This is unselected reusable CPU code, not a captured exit or claim of official authority.

The remaining exact binding gap is mechanical: C228131 is `enter_road`; both exported `exit_road` candidates C62472/C62507 have empty `candidate_ego_parties`, and `runtime/scenario_pipeline/worker_exchange/branch_coverage.py` rejects supplemental assignments whose actor is absent from that list. The current frozen sources therefore cannot select a `motor_vehicle_driver` exit package by editing this assignment. A source-validated catalog/actor binding is required before preparing and strictly checking the two selected exit cases, public and saved chains, delivery/comparison audits and semantic proposals. Entry readiness remains as previously proved; this assignment remains `partial`.

## 2026-11-27 outbound acquisition continuation

`native/exit_runner.py` now requests an original 600-frame, 20 Hz motor-vehicle
route from the authored highway toward the frontage road. It configures and
joins four source cameras, records body poses, frame maps and controls, and
retains the Native world restore and lifecycle seal. Its `check()` enforces the
C62507 / NRS-484B-587-1 / motor_vehicle_driver candidate identity, exact exit
case suffix, duration, camera names and controller gain. The runner does not
assert actor eligibility or physical completion. `tests/test_exit_candidate.py`
exercises the indicated and outside controller requests and rejects the frozen
C228131 entry identity and mismatched case suffix. All eight package tests pass
with exit code 0 in `exit-candidate-tests.log` (SHA-256
`c30577b8adddde95e8b161ea59b1b75f038a5f9527b3b94af4abbe8a6d4b2c67`).
`native/exit_finalize.py` now hashes all four camera sources and requires the
device review to bind the exact overview bytes. A changed overview source is
rejected even when the frame map is unchanged; video decode and actual pixels
remain unverified. Current finalizer SHA-256 is
`e8b09dd576c9faf2c44b0f9d9cd40d1cace8393179f715ecccb190bab4a934ed`.
The `exit-candidate-proposal.json` binds this acquisition
runner and finalizer and remains explicitly unselected (SHA-256
`a7400e5f8ca1f5cd68ae8c2d96a7c7c9058975632866dde7362ccc9dcbd55194`).

Resume after a source-validated same-role exit cell binding: adapt this runner
and finalizer to that exact assignment, create indicated/outside exit cases and
their comparison, run each primary and justified fallback through current
`runtime.py offline`, `runtime.py compatibility` and recorded-only processing,
then bind semantic, physical, delivery and comparison CPU proofs. Run the exact
assignment strict gate before changing status to ready. Original Native lane
connectivity, official device authority, pixels and actual exit remain local
physical and source review tasks.
