# C158196 CPU handoff — NRS 484B.307(6)(a)

Status: **partial**. The selected branch is a steady-yellow warning sequence on the one-way-to-two-way signalized approach. The exact law says traffic facing steady yellow is warned of termination or imminent red and must not enter when red is exhibited. Frozen `evidence.json` has zero accepted recordings; no reuse is claimed.

`case-plan.json` has before/at/after red-onset body-entry comparisons, plus a planned stop-on-yellow contrast. `red_entry_measurements.py` joins original video frames to Native signal/vehicle history, requires the governing signal and lane IDs, uses a sourced intersection polygon and complete ego body vertices, identifies the first Yellow-to-Red transition and first body entry, and reports their time difference. It treats entry on the first red frame as red exhibited. Two CPU tests cover before/at/after timing and rejection of a missing red transition or stale frame map; see `cpu-tests.log`. The present module expects body entry, so the stop-on-yellow case needs an additional finalizer branch.

Next CPU work: implement the actual governed-signal phase controller and ego approach/stop controller, retain head-facing and map evidence, collect all four source cameras and raw histories, finish saved finalizer including no-entry case, and implement three physical-risk fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility, saved-processing and assignment strict proofs. Actual signal-head visibility, realized phase and motion remain later physical checks; the listed construction and proofs are worker-owned CPU work.

The pinned CPU preflight passes. No frozen input, runtime or batch file was edited.

Checkpoint: assignment-scoped `worker_check.py --complete` passed; see `assignment-check.log`. The batch strict gate then failed at missing C177008 result in `strict-gate.log`; that assignment has since received a partial checkpoint.
