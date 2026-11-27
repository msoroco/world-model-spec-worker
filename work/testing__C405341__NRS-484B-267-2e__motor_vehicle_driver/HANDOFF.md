# testing__C405341__NRS-484B-267-2e__motor_vehicle_driver

Status: ready for original GPU delivery under the pinned runtime. Exact assignment strict CPU gate passed; no original capture or legal verdict is claimed.

Exact clause: NRS 484B.267(2)(e), including visible movement/hand-signal preparation under subsection (4). Frozen accepted evidence has zero recordings; no original lane or conditional-context evidence is reused.

Twelve selected exact cases and ten controlled comparisons are in case-plan.json. They cover available nonadjacent lane use versus adjacent use; traffic, roadway, weather, distinct fallen-cargo other-condition and law-enforcement direction circumstances; emergency/regulatory target; moving versus visible preparation cues; flashing and approach activation. No numeric safety or possibility threshold is invented.

Construction: build_constructions.py materializes 12 exact inline bundles and four physical fallbacks. emergency_construction.py gates reviewed Native lane graph, connected routes, qualifying equipment, authorization, original condition sources and controller actions. runner.py opens only a hash-bound reviewed Native adapter and restores/readbacks world state. lane_probe.py and analysis.py require all 900 original frame/camera joins, lane and condition histories, and source hashes. Diagnostic recipes under diagnostics/ are synthetic software fixtures only.

CPU proofs: 16/16 exact primary/fallback runtime.py offline checks; 16/16 current-runtime positive and negative compatibility checks; prove_physical.py exercises three physical state outcomes and lifecycle for all 12 cases; 12/12 recorded-only saved replays; 10/10 independent construction/audit unit tests; negative missing-original-source gates for all 12; source-bound independent original delivery and ten-comparison audit commands. Direct production queue intent is in gpu-queue-proposal.json. cpu-strict-assignment.log records the successful exact strict command. All 326 returned files are UTF-8, at or below 2 MiB, and have clean whitespace/EOF checks.

Remaining delivery work: Native execution against reviewed sources, original four-view pixel and lane-context audits, independent comparison receipts, physical acceptance and legal possibility/safety judgment. The parent lead integrates the queue proposal after its independent assignment check.
