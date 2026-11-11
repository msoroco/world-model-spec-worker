# C102304 / NRS 484B.710 worker handoff

Status: **partial**. The package has ten exact CPU software-proved cases, each with primary plus three distinct fallbacks. Delivery-wide semantic, physical-outcome, audit, and queue bindings remain incomplete. No CARLA motion, physical distance, visible device state, camera visibility, or legal acceptance is claimed. Pinned CPU dependencies, FFmpeg, and Lean 4.28.0 are available and pass their preflights.

## Source and branches

The frozen assignment is `inputs/heldout__C102304__NRS-484B-710__motor_vehicle_driver/assignment.json`, SHA256 `65306863f6f9c06d3529c3d84d4f9aa701426fcc3ee6e2c896ea225ff19f9966`. NRS 484B.710 addresses an ordinary driver following a traveling fire apparatus responding to an alarm closer than 500 ft, driving to or parking within 500 ft of apparatus stopped in answer to an alarm, and an authorized-emergency-vehicle-on-official-business exception. Alarm purpose and authorization are sourced premises; lamps and siren do not prove them.

`case-plan.json` has ten exact cases and four comparisons. The bundled cases are traveling-follow 499/500/501 ft, stopped drive-to 450/500/550 ft, stopped park 450/500/550 ft, and the authorized emergency vehicle on official business at 500 ft. The exception is paired with the ordinary-subject traveling 500 ft case; its source declaration remains an authored premise for later local review. The accepted frozen 450/550 ft traveling-follow summaries are cited in `case-plan.json.evidence_review`; their commanded gaps are not substituted for original full-footprint measurements. They do not cover the exact boundary, stopped branches, or exception. The exported inventory lacks original video/trace bytes, so accepted evidence remains retained for local review.

## Construction and source measurements

`execution-manifest.json` SHA256 `c1a0970ddf336eb4f09e0fc32260ff6ff29799deb4250c55abcaef7208ec587a` binds ten exact cases and 40 candidates. Every candidate has an exact offline log, positive compatibility receipt, negative missing-source log, and saved-only processing path. Pinned candidate validation (`required=True`, `candidate_count=4`) and `package_compatibility.check_receipts` pass across all ten cases.

The traveling runner selects a Native crest route, follows a moving fire apparatus, and captures 20 Hz synchronized original frames, footprints/state, and four RGB streams. `fire_finalizer.py` derives `fire_gap_ft.jsonl` from retained original full body footprints after acquisition. `fire_comparison_audit.py` recomputes the below/at/above comparison. The stopped runner controls drive-to or parking toward a stationary apparatus. `stopped_finalizer.py` derives `fire_centre_distance_ft.jsonl` from retained original footprint centers after acquisition; it does not use a commanded target as a measurement. `delivery_audit.py` checks original source hashes and full four-camera decoding.

`cases/authorized_emergency_at500/construction.json` selects a Native firetruck blueprint for the subject and requires both explicit authorized-emergency and official-business context booleans; it does not infer those from emergency lights. The saved-only proof retains that context in the measured result alongside the 500 ft full-footprint gap. The diagnostic context is synthetic and does not prove real dispatch authority or actual official business. `make_exception_case.py` and `prove_remaining_stopped.py --exception` generate and prove its four exact candidates.

Fallback1 densifies route sampling from 5 m to 2.5 m if a valid crest route is not found. Fallback2 lowers controller gains after a measured attainment failure. Fallback3 shifts the approach camera mount after source-pixel review finds a required body missing. Each retains the exact case target, cameras, duration, and observations. `tests/test_first_candidates.py` and `tests/test_stopped_candidates.py` inspect actual source changes. The diagnostic fixture adds newly authored synthetic participant footprints/state/context and four videos. The pinned example provides Native graph/trace scaffolding only. Fixture motion and visibility are software diagnostics, not physical evidence.

`case-plan.json.source_observation_mapping` covers all nine frozen source terms with original source references and derived channels. `tests/test_all_comparisons.py` independently recomputes stopped drive-to and parking below/at/above bins and the ordinary-versus-emergency exception from retained source hashes; it rejects changed original footprint bytes. These synthetic comparisons establish software behavior only.

## Proofs and latest gate

- `.venv-cpu/bin/python runtime.py preflight` passes; `work/_shared/preflight.log`, SHA256 `ed8a33584479af39983e89d5f944cb7a6780d3802eb7735b79a55caebf29eea2`.
- `.venv-cpu/bin/python -m unittest discover -s tests` passes; `work/_shared/repository-tests.log`, SHA256 `a68310218bcf9e28bd7c22521b1b4856065d395a5f8b0b85a1aa2112306925db`.
- The pinned Lean decoder was built by `runtime.py build-decoder`; executable `.runtime-work/fire-decoder/.lake/build/bin/adapterCheck`.
- `.venv-cpu/bin/python -m unittest discover -s work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/tests -v` passes **55 tests** in `cpu-tests.log`, SHA256 `ca0df269080ad4a7473655f8db3a351205a1d74a094654dbe8a9a81813c6f4cd`. Saved-processing tests start from fresh raw diagnostic sources and run all 40 selections through analysis, Native validation, Lean conversion, rendering, and complete video decoding. Original source hashes remain unchanged and derived gap/center streams are regenerated after capture. Tests check measured values, separately sourced exception context, and reject altered traveling originals.
- `.venv-cpu/bin/python worker_check.py --assignment heldout__C102304__NRS-484B-710__motor_vehicle_driver --complete` passes; `worker-check.log` records the current checkpoint. The assignment strict gate (`strict-gate.log`) and batch strict gate (`work/_shared/batch-strict-gate.log`) still reject `partial` status. The status stays `partial` until the remaining CPU preparation passes.

## Remaining worker-owned CPU work

Finish canonical semantic proposal review, physical-outcome fixtures, independent delivery audit bindings, and the ordered GPU queue. Run their affected proofs, then rerun the assignment and batch strict delivery gates. These are worker-owned construction/proof tasks, not external blockers. The latest strict batch gate rejects 49 partial packages and 2 ready packages; this C102304 package remains partial.
