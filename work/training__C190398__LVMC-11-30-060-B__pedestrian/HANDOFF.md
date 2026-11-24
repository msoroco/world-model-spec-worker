# training__C190398__LVMC-11-30-060-B__pedestrian

Status: partial semantic foundation. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

LVMC 11.30.060(B); with 11.30.060(C): Any pedestrian crossing a roadway at a point where a pedestrian tunnel or overhead pedestrian crossing has been provided shall yield the right-of-way to all vehicles upon the roadway. The foregoing rules in this Section shall have no application under the conditions stated in Section 11.30.070 when pedestrians are prohibited from crossing at certain designated places.

Cell: pedestrian_overpass / straight / other_vehicle; actor: pedestrian. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

pedestrian crossing roadway where overhead crossing provided; same approaching roadway vehicle Vary only `pedestrian_yield_to_roadway_vehicle` (category) across ['yield', 'enter_ahead']. Measure physical overhead crossing, road entry, vehicle approach and pedestrian yielding. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Frozen overpass cell does not establish a pedestrian crossing the roadway. Cell maneuver straight on overpass may not entail roadway crossing; Section 11.30.070 exception needs separate review. Resolve exact statutory branches and external authority from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.

## Current CPU proof

`native/build_semantic_foundation.py` derives draft relevance, statutory template, three judgment-observable contracts, and cell bindings directly from the frozen law and assignment. It validates all seven instances through pinned `batch_pipeline.stages.validate`. The indexed stage hashes are in `proposals/semantic-foundation-index.json`; `proposals/semantic-foundation-proof.json` binds the builder, passing CPU preflight, stage validation and assignment-scoped complete-check logs. `case-plan.json.source_observation_mapping` now names the proposed raw and derived sources separately for each exported observation term. These are requirements for future original data, not acquired measurements.

The overpass condition needs an actual roadway polygon, pedestrian route and grade-separation footprint at the crossing point. The yield duty needs a complete vehicle inventory and synchronized interaction history; hard braking alone is not a legal conclusion. The Section 11.30.070 exception remains a separate source and scene applicability question. Next CPU work is to make the planned yield/enter-ahead pair into exact cases, choose and test one primary construction with actual four-camera acquisition and saved processing, then test three distinct fallbacks and independent audits. Keep this result partial until the assignment-scoped strict gate passes.
