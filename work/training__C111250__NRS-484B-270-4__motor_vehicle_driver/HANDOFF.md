# NRS-484B-270-4 at C111250

Status: partial; authored facility geometry and saved-body CPU comparison pass pinned offline preflight.

Actor: `motor_vehicle_driver`. Frozen cell: `intersection` / `travel` / `centerline`.

Exact source: NRS 484B.270(4). The full text and source hash are retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branch: Intersection entry and passage within a designated facility.

Controlled variable: `vehicle occupancy of bicycle facility through intersection`. Requested pair: cross bicycle facility only as permitted by subsection 3; enter intersection while traveling within bicycle facility. These are construction requests, not measurements or legal verdicts. The baseline is unselected.

Statutory branch dispositions: 2. Review each exception and dependency against the exact text before physical selection. Accepted membership rows: 0; no source-hashed equivalence receipt is available, so reuse is unclaimed.

Open work: Authored centerline/cycle-lane geometry and two offline CPU preflights now exist. Full Native acquisition, source-bound saved finalization, compatibility, independent audit and physical review remain unverified.

Resume: build Native geometry, actor control, cameras and mandatory capture for each runnable branch; prepare four distinct source-preserving constructions per selected case; run exact pinned-runtime offline and compatibility checks, saved positive/negative fixtures and an independent audit. Set `ready` only after those CPU proofs pass.

Source-context review: Preserve the subsection 3 exception as unresolved dependency. The comparison must measure intersection occupancy inside the bicycle facility, not merely a boundary touch.

## Cycle-facility construction checkpoint, 2026-11-23

`native/facility.py` authors an intersection with its centerline intact, a motor through lane beside it and a continuous two-meter biking lane across the junction. `body_overlap` computes the saved four-corner motor-vehicle body overlap with the cycle-lane/intersection region and retains measured speed; it does not set a legal cutoff or decide subsection 3. `native/runner.py --check` distinguishes a through route outside that lane from a body placed within it. Both exact controlled-case draft constructions pass pinned `runtime.py offline` with 600-frame/20 Hz plans and changed-body/unknown-case negatives. The source and log hashes are in `cycle-facility-cpu-proof.json`. No Native world, official facility designation, original body/pixels, exception circumstance or legal outcome was observed.

Remaining worker CPU work: implement actual four-camera Native acquisition and saved finalizer from raw body, road and facility sources; test positive/negative compatibility and comparison, distinct physical fallbacks, and selected delivery proofs. Source review must resolve NRS 484B.270(3) exceptions before any lawful-control label.

## Current v2 retained-source pair, 2026-11-24

Both exact controlled cases now have 600 source-hashed original-frame/body/trace/video-map rows and four synthetic camera videos. The primary stays outside the authored cycle lane (0 of 108 intersection body frames overlap); the contrast occupies it (108 of 108 overlap). The independent row audit is `current-v2-pair-audit.json`. Both public compatibility checks passed, including removal of the required `body-history.jsonl` source; both actual saved-processing runs passed with `recorded_only=true` and `missing_evidence=false`. Receipts are copied into this package. These are unselected synthetic diagnostics.

- primary: case `training__C111250__NRS-484B-270-4__motor_vehicle_driver__controlled_1`; manifest SHA `75b29d8db5eecf2629c52f4cff1001db53ecc259dceb9b3f3086c0398c1ecaa5`; recipe SHA `6e97121c9f4c4fa6108663d3ba92d6e09837d1c21b4d2966fda1e710f839fc71`; compatibility receipt SHA `3d0b16173c3fce6b7125b9123e00cedf71af14fd35a64986e4410cc46e7eac9e`; processing receipt SHA `a646e328162425a18529c64e9065f9eb1a06039c8119d13dc06dad251a8f8a47`.
- contrast: case `training__C111250__NRS-484B-270-4__motor_vehicle_driver__controlled_2`; manifest SHA `d81e609a5aac722dec5e3bd5e4065b45b28a39c2765670d023767872293c1aa4`; recipe SHA `6fa7d923e54ddf8be8c7f4cec60bb76d0807e9ce3b596283a8b142ab6c53866c`; compatibility receipt SHA `02e99b9082e75d8335da3534ee4dde40c196f98962abf73907c8f9f7f2e73e10`; processing receipt SHA `e73d423ab510e80e2fcb7de68a2de02b2cf27badfeb27b3bcd8be568de931011`.

Reproduce primary public compatibility with `.venv-cpu/bin/python runtime.py compatibility --manifest work/training__C111250__NRS-484B-270-4__motor_vehicle_driver/current-v2-primary-manifest.json --case training__C111250__NRS-484B-270-4__motor_vehicle_driver__controlled_1 --output .runtime-work/owner195/recheck-primary --library runtime/pipeline/library --validator .runtime-work/decoder-update16/.lake/build/bin/adapterCheck`. Use `current-v2-contrast-manifest.json` and `__controlled_2` for the paired case, each with a fresh output path. Scratch and generated fixtures belong under `.runtime-work/`.

Remaining CPU work: four distinct physically meaningful branches and process-saved proofs per selected case, actual Native acquisition and original sensor/body readback, official bicycle-facility designation, review of subsection 3 exception circumstances, physical fallbacks, and selected delivery/strict gate. No accepted membership, legal verdict, or physical success is claimed.
