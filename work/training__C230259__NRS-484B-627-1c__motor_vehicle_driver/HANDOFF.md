# NRS-484B-627-1c at C230259

## 2026-11-23 saved-route CPU continuation

The exact supplied clause conditions the alternate-route duty on both slow
driving that impedes traffic immediately behind and a controlled-access
highway. "Whenever possible" requires a usable, connected alternate route;
the selected witness pair alone does not resolve the no-route exception.

`route_cpu.py` constructs two 600-frame, 20 Hz, 30-second **synthetic** route
traces. Both carry the same two immediately following vehicles and a route
graph with a connected exit-to-destination alternative. One request leaves
at the usable exit; the other passes it. The saved reducer checks source
hashes, all frame/time joins, follower order and relative speeds, a full exit
window, and route connectivity. Two positives and five negatives pass. The
negatives remove graph connectivity, remove a follower, shorten the exit
window, inject an unsupported route hop, and break the track source hash.

Command: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python
work/training__C230259__NRS-484B-627-1c__motor_vehicle_driver/route_cpu.py
--prove` (exit 0; two positives and five negatives). Script SHA-256
`7a222398243fa951b212c2f0ec1fc4fdce2d8a554c08a07019c7589d8cab5fe8`;
`route-cpu-proof.json` SHA-256
`a3d84c4d39e6c3ea62ea3f9ae7bc0a31d33cec59066f628c41a927143fbc5abc`.
The scoped `.venv-cpu/bin/python worker_check.py --assignment
training__C230259__NRS-484B-627-1c__motor_vehicle_driver --complete`
checkpoint passed (exit 0, static checks passed). Generated facts explicitly
mark Native observation, controlled-access designation, and legal impeding
judgment unverified.

Next CPU work: build a connected Native exit/alternate route and slow ego with
actual following traffic; retain four original synchronized camera streams and
map/trajectory sources; bind all four selected and exception cases in exact
constructions; implement saved finalization for both route-possible and
no-route contexts; run pinned offline, positive/negative compatibility,
saved-only, semantic, and independent audits. Current result remains `partial`.

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `travel` / `other_vehicle`.

Exact statutory source: NRS 484B.627(1)(c). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Alternate-route duty on a road established separately as controlled access.. Planned comparison variable: `slow_vehicle_alternate_route`. Requests: slow driver takes available alternate route at usable exit; slow driver passes available exit and remains on controlled-access road. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject drives so slowly as to impede the traffic behind; the highway is a controlled-access highway; an alternate route is possible.

Timing to retain: 'use alternate routes whenever possible' is a route-level duty: it cannot be judged from a short clip, only from a trace long enough to contain a usable exit.

Exceptions and numeric alternatives planned: where no alternate route is possible.

Unresolved judgment or rule composition: what counts as an available alternate route is a map and journey question, not a scene observation. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-26 current-runtime continuation

Four exact primary and fallback1 Native route constructions are materialized. The route reducer checks the original 900-frame trace, all four camera frame joins, OpenDRIVE topology, actor identities, same-frame follower positions and observed route occupancy. Three saved-route positives and seven negatives pass. All eight selected offline checks pass. Current-runtime compatibility passes for witness_1 primary and fallback1 and witness_2 primary; the remaining candidates are still processing. The canonical semantic stage chain passes its CPU validator for all four cases and explicitly leaves the three source-dependent legal judgments unresolved.

The only source-shaped compatible recordings are diagnostic fixtures. No accepted original Native recording supplies independent controlled-access designation, actual impediment, or practical alternate-route availability. Physical completion, delivery acceptance, and legal outcome remain unverified. Status stays partial pending the remaining positive/negative compatibility, saved-only, physical/lifecycle and independent audit proofs.

Current exact proof checkpoint: all eight offline and all eight current-runtime compatibility positive/negative checks pass; the canonical semantic chain, both independent diagnostic comparison positive/negative checks, all four physical/lifecycle diagnostic receipts and all four independent delivery-audit predicate selftests pass. Witness_1 primary saved-only reprocessing passes with original diagnostic sources preserved. Remaining CPU work is the seven selected saved-only candidate replays, final manifest binding and stable-byte strict assignment gate. No original Native recording or legal determination is claimed.

## 2026-11-26 completed CPU preparation

All four exact selected cases and both primary/fallback1 candidates per case have passed exact offline construction, positive/missing-required-source-negative compatibility, and saved-only recorded-only processing with preserved original diagnostic source hashes and four-view frame joins. The eight saved processing receipt files and hashes are bound in `result.json`. CPU unit tests (4), pinned runtime preflight, semantic stage validation (8 stages, four cases), four independent delivery-audit selftests, four physical/lifecycle diagnostic receipts, and both comparison positive/negative checks passed. The validated execution manifest SHA-256 is `deea7e47d17c1e5ca8e719ce9c687801783e0a63adf6c60b84f8a1f86b71f92c`. The scoped partial worker check passed before the final strict run.

The exact original NRS 484B.627(1)(c) requires source-observed traffic impeded immediately behind, an independently established controlled-access highway, and a practically usable alternate route. The four exact cases separate taking/passing a possible route from no-route exceptions. The construction graph and synthetic speeds are diagnostic only. Actual Native motion, decisive original pixels, independent designation and route availability review, physical/lifecycle completion, and canonical delivery acceptance remain local GPU and reviewer work. No legal verdict or accepted recording is claimed by these CPU proofs.
