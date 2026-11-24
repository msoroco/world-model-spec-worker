# training__C111325__LVMC-11-40-130__cycle_or_scooter_operator

Status: **partial CPU implementation checkpoint**. No condition is selected for delivery. No original bicycle execution, physical-condition measurement, or reasonable-and-prudent legal verdict is claimed.

## Source and current construction

Exact law: “It shall be unlawful for any person to operate a bicycle at a speed greater than is reasonable and prudent under the conditions then existing.” The selected witness asks for bicycle speed during a stop-sign intersection approach. The source topics are retained in `case-plan.json`; no accepted recording was present in the frozen local membership snapshot.

`native/speed.py` authors two 600-frame, 20 Hz, 30-second synthetic bicycle approach requests. Both start 50 m before the stop line and stop 2 m before it. The stop sign, visibility, dry road, pedestrian absence, route, and stop line are held fixed. Requested peak approach speeds are 3 and 5 m/s; speed in the proof is recomputed from consecutive positions, not labeled original CARLA velocity. The faster request reaches the common stop position at frame 222 versus frame 337 for the slower request. These speeds are engineering contrast values, not legal thresholds.

`prove-speed-source.py` measured both full traces and rejected six damaged-source or false-authority variants. `native/build_runtime_offline.py` bound frozen law and source hashes into two **unselected** draft constructions. Both pass the current pinned `runtime.py offline` runner under `.runtime-work/c111325/offline-a` and `offline-b`. `audit-speed-current.py` independently joins the frozen law, case plan, source hashes and construction hashes, recomputes speed and stop timing, and checks fixed conditions. Proof and log SHA-256 values are in `result.json`. The assignment-scoped complete checker passed; its strict variant failed on the partial package.

## Remaining CPU work

Implement an actual bicycle Native mechanism rather than substituting a motor vehicle; obtain contemporaneous source measurements for speed, visibility, weather/surface, curvature, users and clearance. Provide four synchronized cameras, source-only current compatibility and actual process-saved positive/negative checks, selected case construction and risk candidates, semantic proposals, independent delivery and comparison audits, then rerun the strict scoped gate. Preserve the legal judgment “reasonable and prudent under the conditions then existing” as unresolved; a measured speed or surrogate cannot decide it on its own. Keep this result partial until all CPU preparation proves ready.
