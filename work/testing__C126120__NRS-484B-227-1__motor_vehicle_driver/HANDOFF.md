# C126120 CPU handoff — NRS 484B.227(1) U-turn

Status: **partial**. Fixed cell: median opening, U-turn and median barrier. The law permits crossing or turning through an opening, crossover or intersection established by public authority. The selected branch includes a multiple-movement U-turn.

`case-plan.json.evidence_review` reads both accepted metadata inventories. They identify opposite-roadway/right-roadway cases, 556 frames and a passing decoder, but no exported raw trace, video or audit proves a U-turn or authority-established opening. No original is replayed or claimed sufficient. Conditional new U-turn cases retain that gap.

`barrier_construction.py` calls Native `world.try_spawn_actor` for two barrier sections, checks realized footprints straddle and do not close the opening, then cleans up. `uturn_measurements.py` joins original frame/body/gear records, detects opening and blocked-divider overlap, start/end roadways, heading change and forward-reverse-forward movements. Three CPU tests pass, including a negative divider crossing, stale frame, missing gear and Native cleanup. Turn angle and gear changes are descriptive; authority status and legal result remain unresolved.

Next CPU work: source-review accepted originals for equivalence and public-authority establishment. Construct exact Native U-turn path and controlled multiple-movement sequence; implement runner, four raw cameras, saved finalizer, three distinct fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility, saved-processing and assignment strict gates. These are worker-owned CPU actions. Actual motion and visibility remain later physical checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C126120__NRS-484B-227-1__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C126120__NRS-484B-227-1__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C147311__NRS-484B-220-1__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.
