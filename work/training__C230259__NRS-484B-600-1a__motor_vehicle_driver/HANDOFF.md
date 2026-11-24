# training__C230259__NRS-484B-600-1a__motor_vehicle_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.600(1)(a): It is unlawful for any person to drive or operate a vehicle of any kind or character at: A rate of speed greater than is reasonable or proper, having due regard for the traffic, surface and width of the highway, the weather and other highway conditions.

Cell: road / travel / other_vehicle; actor: motor_vehicle_driver. Frozen witness count: 4. Membership rows: {'demo-train': 37, 'full-train': 37}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

same traffic, surface, width, weather, visibility and other highway conditions within each sweep Vary only `measured_speed` (m/s) across [8, 12, 16, 20]. Record speed, traffic interactions, pavement and weather throughout; sweep physical speed without verdicts. The definitions are not selected recordings, and requested settings are not measured results.

## New CPU construction and proof

`proposals/build_semantic.py` constructs six source-bound draft stages: relevance batch, relevance, exact-law template, judgment observables, bindings and cases. The cases preserve the four planned requested speed values and keep measured speed unknown. The `reasonable or proper` sweep remains explicitly incomplete pending source review and physical feasibility. `proposals/test_semantic.py` validates all six against the pinned runtime stage contracts; `proposals/semantic-stage-cpu-proof.json` binds their hashes. Validation log SHA-256: `c8e266de88b71cbd70075d3f82793293c933e730b683deb7b65599d73a41ce99`.

`analysis/speed_conditions.py` measures original-frame speed and joins contemporaneous participant, road, weather and four source-camera frame identities. It has no legal cutoff. `analysis/test_speed_conditions.py` passes a 600-frame, 30-second `synthetic_native_sample` diagnostic and rejects missing camera, weather, traffic and a short capture. Log SHA-256: `94f37debcfbef1af44fab4c3b106e4bb0d06282ee2eb9a45169a1b4fb8b40ee0`. This is a CPU software proof only; its invented speed is not original Native velocity.

The assignment-scoped checkpoint `.venv-cpu/bin/python worker_check.py --assignment training__C230259__NRS-484B-600-1a__motor_vehicle_driver --complete` passes static checks. The strict ready gate has not passed.

## Remaining CPU work

Review every accepted recording's source-backed facts and equivalence before deciding which comparison branches need new captures. Resolve the speed sweep's full source-grounded range and separate traffic, surface, width, weather and other-condition comparisons. Build exact selected-case Native construction, primary and three distinct risk fallbacks where the active delivery contract requires them, synchronized four-camera capture, source-bound saved finalization, positive/negative compatibility, and independent delivery and comparison audits. Revalidate all against the current runtime and run the scoped strict gate before any ready label. Original physical speed and camera evidence must be checked later in CARLA; the qualitative statutory judgment remains unresolved.
