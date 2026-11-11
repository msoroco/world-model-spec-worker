# Handoff: heldout__C136014__NRS-484B-113-1__motor_vehicle_driver

## Exact frozen scope

NRS 484B.113(1): a driver shall not back unless the movement can be made with reasonable safety and without interfering with other traffic. C136014 is a narrow-road reverse maneuver with another vehicle; actor is `motor_vehicle_driver`. The law supplies no numeric safety or interference cutoff.

## Constructed exact cases and CPU proofs

Three exact cases isolate clear traffic with steady speed, close traffic with steady speed, and clear traffic with braking. Each has a Native CARLA runner, four synchronized cameras, retained backing history, source-bound finalizer, measurement contract, diagnostic recipe, and three distinct risk-triggered fallbacks. All 12 primary/fallback bundles passed `runtime.py offline`, refreshed positive and missing-source `runtime.py compatibility`, and refreshed positive and missing-source `runtime.py process-saved` with the pinned Lean decoder. The associated logs and SHA-bound compatibility receipts are in `execution-manifest.json`. These synthetic CPU fixtures do not establish physical backing acceptance.

`comparison_audit.py` independently joins original history, trace and video-frame map, recomputes reverse motion, minimum center distance and traffic speed change, checks fixed road and ego trajectories, and rejects swapped case sources. `delivery_audit.py` checks exact case identity, both participant sources, complete frame joins and four full video decodes; `prove_delivery_audit.py` confirms removal of `backing_history.jsonl` is rejected for each case. Fixture `physical_completion_check` remains false.

`physical_fixture.py` exercises complete reverse motion, incomplete motion and missing evidence against original-shaped fixture streams for each exact case. `lifecycle_fixture.py` runs each bundled runner against mocked Native ownership and verifies capture closure, encoder closure, settings restoration and saved-only processing order. These proofs are protocol fixtures only; actual Native completion and original-pixel visibility remain for the delivery operator.

A source-hashed seven-stage semantic chain (`relevance_batch`, `relevance`, `template`, two `judgment_observables`, `bindings`, `cases`) validates against the exact frozen law and cell. The canonical cases draft selects the three exact cases and a shared baseline. Its two judgment sweep specifications are explicitly **incomplete** because fixed physical grids, Native feasibility evidence and the original traffic-response recording channel are not yet encoded. This is the remaining CPU preparation gap; no legal judgment is inferred from the measured center distance or braking.

The exact execution manifest, semantic chain, package compatibility receipts and delivery acceptance contracts pass direct CPU preflight (`readiness-preflight.log`). Three four-view delivery audits and two independent comparisons pass their positive and rejection proofs. Eight unit tests pass (`cpu-tests.log`). `.venv-cpu/bin/python worker_check.py --assignment heldout__C136014__NRS-484B-113-1__motor_vehicle_driver --complete` passes. The scoped strict `--require-delivery-ready` check fails while `result.json` truthfully remains `partial`.

## Next CPU work

1. Complete fixed judgment sweep grids for both qualitative phrases with source-backed feasibility, materialize every selected sweep case, and add its exact construction, fallback and CPU proofs. Add an original traffic speed-response channel if required by that sweep; regenerate every affected bundle and receipt.
2. Re-run the full exact-case offline, compatibility, saved-only, physical protocol, comparison and delivery audits after the expanded case/recording contract. Update source hashes in the semantic index and manifest.
3. Run the scoped strict gate and mark `ready` only after it passes. Original Native physical motion and visual body review remain part of later delivery acceptance.
