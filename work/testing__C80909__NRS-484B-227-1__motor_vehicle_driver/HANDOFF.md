# C80909 CPU handoff — NRS 484B.227(1)

Status: **partial**. The frozen branch label mentions a U-turn, but the witness binds this divided-road/left_turn/other_vehicle cell to the distinct 90-degree left-turn alternative. C126120 remains the assigned fixed U-turn cell. This package makes no U-turn coverage claim. The exact law requires the right-hand roadway and forbids crossing a dividing space or turning except through a physical opening or public-authority-established crossover/intersection. The frozen evidence inventory has zero accepted recordings.

`case-plan.json` maps left turn through a physical opening, crossing the blocked divider, established crossover and right-roadway continuation. `barrier_construction.py` makes actual Native spawn calls for two barrier sections, checks their realized footprints straddle and do not close the opening, and destroys owned actors. `divider_measurements.py` joins original frames to complete ego/other bodies, right-hand and destination roadways, divider/opening polygons and observed heading change. It reports opening versus blocked-space occupancy without a legal or public-authority conclusion. Three CPU tests pass in `cpu-tests.log`, including Native spawns/cleanup, a 90-degree route through the opening, blocked-space overlap, stale frame and missing source rejection.

Next CPU work: source a real divided highway, roadway boundaries and public-authority crossover status where relevant; construct ego left-turn and other-vehicle routes/controllers with safe barrier clearance; capture all four raw cameras and original body/road/barrier sources. Implement saved finalizer and measurement contract, three distinct physical-risk fallbacks per selected case, canonical semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Actual barrier clearance, route, authority, motion and camera visibility remain later source/CARLA checks; the listed implementation and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C80909__NRS-484B-227-1__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C80909__NRS-484B-227-1__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C109705__NRS-484B-400-2b__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.
