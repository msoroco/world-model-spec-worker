# training__C111294__NRS-484B-250-1__motor_vehicle_driver

Status: **partial**. No selected delivery cases, CARLA construction, CPU candidate proof, CARLA execution, or accepted recording is claimed.

Exact source: `inputs/training__C111294__NRS-484B-250-1__motor_vehicle_driver/assignment.json` SHA-256 `416cde7667eafc72563ff3681da9de77843de01cbb467cb6a557e81037c716a5`; witnesses: `inputs/training__C111294__NRS-484B-250-1__motor_vehicle_driver/witnesses.json` SHA-256 `de548fc52f4951c5e486de2101774ccb3658a51acc2a3420dc46b1d73c2be20c`. The statutory text and source citation are retained in `case-plan.json`; recovered summary is unreviewed.

Frozen cell: `intersection` / `travel` / `other_vehicle`; actor `motor_vehicle_driver`. Proposed contrast: **entry order and yielding**. 2 unselected planning probes are in `case-plan.json`. Baseline is unselected.

Open construction work: Controlled-device and opposite-direction-left-turn exclusions need separate context checks. Accepted membership cannot be reused without current source-hashed equivalence. 4 unique accepted membership IDs are contextual and have no local source-hashed equivalence proof.

Resume: review exact branch and exception context against law and witness, prove any eligible accepted equivalence, resolve same-cell physical support, then implement four distinct Native candidates for each genuinely selected case. Run runtime offline/compatibility recipes, semantic-stage and saved positive/negative audits, comparison audits, and set `ready` / `delivery_prepared` only after all worker-owned CPU proofs pass. Keep legal standards unresolved pending measured evidence.

## 2026-11-23 source-bound priority checkpoint

Added `native/measure_priority.py` and `native/source-capture-contract.json`. The measurement joins 600 original 20 Hz frame IDs, four decoded and byte-bound source cameras, x/y Native poses, reviewed intersection boundary/highway origins and reviewed device/turn context. It reports measured entry order, priority occupancy when ego enters, overlap and ego speed; device and opposite-left-turn exclusions remain separate observations. The CPU proof in `native/priority-proof.log` passed four synthetic context variants and seven negative source mutations; script and log hashes are in `result.json.priority_cpu_proof`. Synthetic clips are diagnostic only. No accepted membership equivalence, exact selected capture construction, saved processing, independent audit, or physical completion is claimed.
