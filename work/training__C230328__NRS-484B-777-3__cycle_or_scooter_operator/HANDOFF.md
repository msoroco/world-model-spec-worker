# C230328 / NRS 484B.777(3) handoff

Status: **partial**. Accepted memberships: 0. Frozen `road/travel_abreast/cyclist` cell and `cycle_or_scooter_operator` actor retained. Exact source law and hashes remain in `case-plan.json`.

## Construction and CPU evidence

- `selected-primary-construction.json` (SHA-256 `68e8048ad59a14d7fd36b27a7ecf6b4a843a6ef1398e0deddbf3b4caacdf87cb`) is an inline Native primary for two distinct qualifying bicycle riders in `__controlled_1`. `native/runner.py` (SHA-256 `436addbefb8deeb571090e2d3b284620ceec8639e8c0198c676a83fdcb89c0db`) requires reviewed public-roadway, shoulder, bicycle-identity and exclusive-use sources, captures 600 original frames at 20 Hz with four cameras, and records each rider's identity, longitudinal/lateral pose and extent. It has not run in CARLA.
- `measure_abreast.py` (SHA-256 `10b6b21688c55dab70fff7b499611b7876cf08a152f949650519c517f58841ad`) joins source frames and riders, verifies road/shoulder/exclusive-use occupancy, retains each pair's longitudinal intervals, raw overlap length, lateral delta and bearing, and binds original review to four decoded 600-frame camera hashes. It imposes no numeric overlap, distance or persistence cutoff to define "abreast" and returns no legal verdict.
- `prove_abreast.py` tested 600-frame two-rider, three-rider and three-rider convoy fixtures. The convoy has zero pairwise longitudinal overlap despite three riders. It rejects missing exclusive-use review, a rider off the roadway and identity drift; optimized mode also passed. `prove_saved.py` joined four synthetic diagnostic FFV1 sources and rejected a tampered camera hash. These are diagnostic fixtures, not Native evidence.
- Pinned `runtime.py preflight` and selected primary `runtime.py offline` pass (`pinned-preflight.log`, `abreast-cpu-1.log`); offline reports `simulation_started=false`. Assignment-scoped `worker_check.py --complete` passes (`scoped-check.log`). Strict scoped gate fails on truthful partial status (`strict-check.log`).

## Remaining exact work

Build the three-rider `__controlled_2` construction and distinct candidates. Source-review qualifying human-powered bicycles and separate riders, public roadway/shoulder boundaries, exclusive-use designation and occupancy; execute Native capture and independently audit original geometry and statutory outcomes. No three-abreast finding is inferred from a convoy or from an invented cutoff. Electric-bicycle and electric-scooter alternatives remain separate source branches.

Scratch/temporary files are under `.runtime-work/c230328-777-*`; none are under `work/`.
