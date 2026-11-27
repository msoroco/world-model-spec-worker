# C412262 / NRS 484B.490 delivery handoff

Status: `ready` for source-gated CPU delivery preparation. The exact scoped strict gate passed on 2026-11-26; see `strict-gate.log`. Native CARLA capture and original physical/legal acceptance remain pending.

## Authority and case design

The assigned branch is parking by a motor vehicle driver on a narrow public highway where an official traffic-control device prohibits parking. `case-plan.json` records the frozen law, original skills, source inventory, conditional witness, six observable channels, gaps, judgment issues and ten new cases. There are no accepted recordings or judgment-range entries for this exact law and actor. No numerical legal narrowness cutoff is asserted.

The baseline `park_narrow_device` is compared with nine one-factor probes: standing, loading, traveling, no device, unofficial device, outside device extent, wider highway geometry, off-highway placement and reverse approach. These are controlled physical and evidentiary comparisons, not pre-decided legal verdicts. The public-highway boundary and full width, device erection/authority/conformity/extent, parking purpose, responsible person and vehicle must be established from reviewed source records. `highway_scene_construction.py` rejects missing or inconsistent original site packets before any scene is built.

## Executable package

`execution-manifest.json` binds ten case constructions and their output artifacts. `runner.py`, `highway_scene_construction.py`, `highway_observations.py`, `native_capture.py` and `native_output_bridge.py` provide CARLA-lazy construction, controller, four-camera 20 Hz / 45 second original capture, source packet preservation and Native handoff. `saved_finalizer.py` and `analysis.py` process original saved artifacts and reject incomplete source, time, body/road geometry or video evidence. `comparison_audit.py` and `delivery_audit.py` independently inspect physical and contrast evidence. The code retains the reviewed source bytes in each saved recording. Diagnostic fixtures are explicitly tagged and cannot establish original physical acceptance.

Each manifest case records no fallback candidate yet because no distinct measurable physical failure mode has been observed without the reviewed original site. The physical risk is documented without an invented alternate scene. `proposals/` contains the semantic proposals. `gpu-queue-proposal.json` contains ten direct Native jobs and nine comparison audit commands for lead integration; its SHA-256 is `e4ba9f1e8106d1cdd3f506266154b60af04831444f3f5eee2b8436e0c93910b6`.

## CPU proof record

- Focused unit tests: 6 passed, including source gate, Native adapter, source preservation, camera cadence/settings lifecycle, geometry and comparison rejection (`cpu-side-tests.log`).
- Offline construction and positive/negative current-runtime compatibility: 10/10 (`cpu-offline-*.log`, `cpu-compat-*.log`, receipt JSON files).
- Physical fixture and lifecycle checks: 10/10, with complete motion accepted, incomplete motion and missing evidence rejected (`physical-*.log`, receipt JSON files).
- Independent diagnostic delivery audit: 10/10 positive and negative (`cpu-delivery-proofs.json` and `cpu-delivery-*.log`).
- Controlled diagnostic comparison audit: 9/9 (`comparison-proof-index.json`, `cpu-comparison-*.log`).
- Saved-only `runtime.py process-saved` replay: 10/10 (`cpu-recorded-*.log` and receipt JSON files).
- Exact gate: `PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.runtime-work/c412262-490-case-proofs-v1/tmp" SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c412262-490-owner" .venv-cpu/bin/python worker_check.py --assignment testing__C412262__NRS-484B-490__motor_vehicle_driver --complete --require-delivery-ready` exited 0 and reported `static_checks_passed: true` (`strict-gate.log`).

## Native follow-up

Supply an independently reviewed original highway/site packet through `SCENARIO_HIGHWAY_SITE_PACKET`, then execute the ten direct jobs in `gpu-queue-proposal.json`. Review the 900-frame four-camera Native recordings, complete physical and comparison audits, and decide legal narrowness, device authority/extent and parking purpose from the preserved source and original pixels. The GPU queue proposal is a local assignment artifact; the lead owns shared queue integration.
