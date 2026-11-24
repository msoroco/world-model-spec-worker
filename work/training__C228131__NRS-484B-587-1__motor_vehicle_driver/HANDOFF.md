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
