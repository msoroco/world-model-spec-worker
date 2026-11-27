# C179776 NRS 484B.587(2)(a) controlled access lane occupancy

## Current return

Status: `ready` / `delivery_prepared` on pinned runtime and frozen update 16. The exact scoped command below passed exit 0 on 2026-11-27; `strict-assignment.log` is its output. This is CPU delivery preparation, not original CARLA execution, physical acceptance or a legal verdict.

```sh
TMPDIR="$PWD/.runtime-work/c179776-tmp" SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c179776-output" PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment training__C179776__NRS-484B-587-2a__motor_vehicle_driver --complete --require-delivery-ready
```

Exact case IDs: `training__C179776__NRS-484B-587-2a__motor_vehicle_driver__probe_a` (remain in marked lane) and `training__C179776__NRS-484B-587-2a__motor_vehicle_driver__probe_b` (requested lateral move beyond it). `case-plan.json` maps the frozen paved-road/travel/lane-marking cell, actor, witness and NRS 484B.587(2)(a) branch to these cases. `execution-manifest.json` selects one original Native construction and three risk-based controller fallbacks per case. The first local GPU command is in `result.json` and requires the original CARLA Python, host, port, DB, run and job variables.

## Law, coverage and uncertainty

`statutory-review.json` separates marked travel, entrance and exit lanes; emergency-required duration; listed vehicle class and authorized signed paved-shoulder manner; and subsection 3's cross-reference to subsection 1(c)(1). The latter is retained for independent review and is not treated as an automatic subsection 2(a) exemption. The frozen assignment supplies no accepted recording IDs. `case-plan.json` claims no reuse or accepted physical/legal result. Original controlled-access designation authority, map/lane and entrance/exit survey, subject class, signs and pixels, emergency source, physical motion, visibility and legal interpretation require local acquisition and independent review.

The two cases hold the route topology, road surface, ordinary vehicle, source policy, four cameras, 30-second duration, longitudinal profile and comparison context fixed. `comparison_audit.py` checks these source identities and frame/control conditions and requires the declared lane-occupancy difference; `comparison-positive.log` and `comparison-negative.log` cover acceptance and a changed-map rejection. Fallbacks remain alternative controllers for the same two cases and do not add recordings or legal outcomes.

## Executable source and proof map

- `native/controlled_access_road.py` builds the two-direction marked-lane/paved-shoulder OpenDRIVE geometry. `runner.py` performs original Native readback, 20 Hz controller/actor/trace capture, synchronized four-view source video, source hashes, encoder closure and world restoration. `finalize_lane.py` joins all 600 frames and four views and derives footprint/exception measurements from saved sources. `native/measure_lane_boundary.py` and `native/measure_exception_context.py` reject missing or mismatched authority, geometry, class, sign, event, frame and body data. The source-shaped survey and construction tests are retained in `native-survey-cpu.log`, `controlled-road-cpu.log`, `native-runner-check-a.log`, `native-runner-check-b.log`, `lane-boundary-cpu.log`, `exception-context-cpu.log` and `saved-lane-cpu.log`.
- `selected-offline-proof.json` records eight passing exact candidate offline checks; `selected-compatibility-probe_*-*.json` and adjacent analysis/negative logs record all eight pinned public compatibility positives and missing-source negatives. These run the saved finalizer, Native/Core/Lean conversion, final renderer and full decode on synthetic source-shaped four-view videos. `selected-saved-probe_a-primary.json` and `selected-saved-probe_b-primary.json` record passing public saved-only processing; no original footage is claimed.
- `proposals/semantic-index.json` binds the relevance, law, observable, measurement, cases and unresolved judgment proposals. `selected-semantic-cpu.log` passes its pinned validator. `physical-proof/probe_a/proof.json` and `physical-proof/probe_b/proof.json` retain synthetic complete/incomplete/missing-motion and lifecycle-order proofs. `delivery_audit.py` independently requires original-source provenance and 600 joined frames, checks all four videos and source hashes, and refuses missing original authority/pixel review. Its positive and missing-source negative logs are under `delivery-proofs/`. `comparison_audit.py` has separate positive and negative logs.
- `current-selected-test.log`, `saved-lane-cpu.log`, `selected-semantic-cpu.log` and `comparison-positive.log` are the four hashed passing test claims in `result.json`. The pinned execution, semantic, physical, handoff and public compatibility validators passed in the exact assignment strict gate. Strict log SHA-256: `908abd6d25a34aa88b6a3d0ed122bf1f2576e1fe91e04ae5e258424de60e66be`.

## Local follow-through

Run the exact first GPU command in `result.json` for each case on an authorized CARLA host. Acquire original authority, map and sign/class/event source packets; inspect four-view original pixels and complete Native motion; decode original media; run the independent delivery and comparison audits on the captured saved sources. Retain unknown or failed branch judgments rather than inferring an exception or violation from synthetic proof. The output-root and scratch variables above keep generated diagnostics outside `work/`.
