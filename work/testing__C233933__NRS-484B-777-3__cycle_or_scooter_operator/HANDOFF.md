# C233933 rider formation handoff

Status: CPU delivery prepared. Four exact cases and three controlled comparisons. The assignment-scoped strict delivery gate passed on 2026-11-26.

Exact NRS 484B.777(3) covers persons riding bicycles, electric bicycles or electric scooters upon a roadway: no more than two abreast, except on paths or parts of roadways set aside for their exclusive use. This package selects source-classified human-powered bicycles for the fixed `cycle_or_scooter_operator` actor. It excludes mopeds, keeps legal abreast and exclusive-use judgments unset, and uses 0.25 m longitudinal tolerance only to check physical formation. No persistence or momentary-overtaking exception is invented.

Cases: `three_roadway_general`, `two_roadway_general`, `three_roadway_exclusive`, `three_path_exclusive`. Comparisons isolate rider count, exclusive-use roadway designation, and exclusive-use path occupancy. `case-plan.json` records exact case IDs and requirement dispositions. The frozen evidence inventory has no accepted exact recordings; its conditional witness requires separate highway, roadway, shoulder, bicycle, moped, sidewalk, rider and designation sources.

`original_runner.py` validates a reviewed Native map and exact case packet, all 14 independent rider source hashes and their file bindings. `abreast.py` requires three or two separate riders and route points on the surveyed occupied surface, outside the shoulder for roadway cases. `rider_adapter.py` spawns source-identified bicycle actors and four cameras; `rider_capture.py` writes 900 original 20 Hz rider, trace, frame-map, measurement and video records. `analysis.py` seals saved-only formation and context measurements. The independent capture and delivery audits require full camera decode and actual pixel review after Native execution.

Eight focused source/formation tests pass. All four selected constructions passed pinned offline, positive/negative compatibility and saved-only replay; all four risk-based speed-scale fallbacks passed pinned offline and compatibility. Four physical/lifecycle diagnostic sets and four independent delivery diagnostics passed. Three comparison protocols passed positive and changed-bicycle-classification negative checks. These CPU diagnostics do not establish original CARLA motion, physical formation, pixel visibility or legal compliance.

Exact gate: `.venv-cpu/bin/python worker_check.py --assignment testing__C233933__NRS-484B-777-3__cycle_or_scooter_operator --complete --require-delivery-ready` (exit 0).

Review anchors: `execution-manifest.json` SHA256 acb1db89b0974c42b49002ec5bfc287ba97870815f81dfe630624c69106b71d4; `gpu-queue-proposal.json` SHA256 d23e7eaea6181600ff7356325b0007d5a4dcd98bc8433b9d0a63e8851998048f; `comparison-proposal.json` SHA256 4a3f5d4b5f8520c9168fdf09a8cbd2ca4de76e5ecd5febe9842200decae8de0a; `cpu-tests.log` SHA256 74a67d5034b8f66d0959abc9fcf5f5d0b1e181904e418e382a9e5e5b69136b1a.
