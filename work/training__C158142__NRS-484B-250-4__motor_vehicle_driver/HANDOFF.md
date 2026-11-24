# NRS-484B-250-4 at C158142

Actor: `motor_vehicle_driver`. Frozen cell: `one_way_to_two_way_intersection` / `travel` / `inoperative_signal`.

Exact statutory source: NRS 484B.250(4). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Post-stop cautious proceeding and yielding.. Planned comparison variable: `inoperative_signal_stop`. Requests: driver stops at the applicable boundary before entry; driver enters the inoperative-signal intersection without a full stop. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the intersection is controlled by a traffic-control signal that is installed with uncovered vehicular signals; the signal is inoperative when the subject enters.

Timing to retain: stop first, then proceed: the halt precedes entry, and the yield is owed to whoever completed a stop earlier; a full halt at the stop line, not a slowing; deciding 'previously completed a stop' needs the other vehicles' histories, so the trace must cover their approaches too.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: 'proceed cautiously' after the stop is a judgement element. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-23 CPU stop-sequence source diagnostic

Added `native/inoperative_signal_measure.py` and `native/prove_inoperative_signal_measure.py`. The saved-source diagnostic requires a source statement that vehicular signals are installed and uncovered and inoperative during entry, then selects the statutory stop reference in order: marked line, near-side crosswalk, nearest view point. It joins 600 source frames at 20 Hz, four pinned camera identities, subject front position and speed, and the other vehicle's stop and intersection history. The 0.05 m/s stop test is an engineering sampling diagnostic, not a statutory definition. It reports source ordering and leaves cautious proceeding and legal judgment unassessed.

Two synthetic fixtures hold the signal, geometry and other vehicle fixed. `witness_1` stops at the marked line at frame 150, after the other vehicle's frame-130 stop, waits through its intersection occupancy, then enters at frame 205. `witness_2` rolls through and enters at frame 180 while the other vehicle is still within the intersection. Both use 600 frames and four camera identities; these are `synthetic_native_sample` diagnostics, not Native motion or pixels. Two stop-reference fallback checks and five missing-source negatives pass.

Commands, each exit 0 with `TMPDIR`, `PYTHONDONTWRITEBYTECODE=1`, and `SCENARIO_PIPELINE_OUTPUT_ROOT` set under `.runtime-work/`:

- `.venv-cpu/bin/python runtime.py preflight > native/current-preflight.log 2>&1`
- `.venv-cpu/bin/python native/prove_inoperative_signal_measure.py > native/inoperative-signal-proof.json`
- `.venv-cpu/bin/python worker_check.py --assignment training__C158142__NRS-484B-250-4__motor_vehicle_driver --complete > native/current-static-check.log 2>&1`

SHA-256: measurement code `c6ad94930bf0da71766b3bcc182cfedfce3f735d28dd8642a91b48b36340efc6`; proof script `c537d2be363f3399459927796d959a8d28a25ecfcb00e6eb7d3ed16c65729652`; proof result `31fe435eb24d45de07a5367a1a0c27b7197f6ba01b302f9f17b85c12bb934ab6`; preflight log `0a55842fee82d0e038cfb47e6a8f061a16c9b6c00c4152ce3c2a4f5192c59b13`; scoped checkpoint log `7a2492c9eaf1d74427237c549e455078c56d6bfaf0037153e00e77bfcc4e9761`.

Next CPU work: implement exact Native signal and participant construction, actual controller for stopped and rolling variants, source acquisition with four video streams, execution manifest, selected measurement/finalizer, pinned offline, positive/negative compatibility, saved-only, semantic and independent audits. Preserve the source-backed stop-reference hierarchy and other vehicle history in those cases. No exact construction bundle yet exists for pinned offline or saved proof; keep `result.json` partial.
