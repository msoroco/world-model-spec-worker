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
