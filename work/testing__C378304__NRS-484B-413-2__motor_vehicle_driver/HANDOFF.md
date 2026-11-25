# testing__C378304__NRS-484B-413-2__motor_vehicle_driver

Status: partial. Five exact case targets and three controlled comparisons are proposed; no new recording is claimed accepted.

Exact law: NRS 484B.413(2) — A signal of intention to turn right or left, or otherwise turn a vehicle from a direct course, shall be given continuously during not less than the last 100 feet traveled in a business or residential district and not less than the last 300 feet traveled in any other area prior to changing the course of a vehicle. This rule shall be observed, regardless of the weather.
Assigned branch(es): Business-district right-turn signaling.
Cell: C378304 (business_district, right_turn, freight_loading_zone); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 4. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Exact case and comparison coverage

- `short80`, `continuous100`, and `above101` request right signal onset at 80, 100, and 101 feet before right-turn course change. This is a below/at/above statutory triple; actual distance is measured only from saved Native samples. The 101-foot case has no existing recording.
- `interrupted` requests a 55–65 foot preturn off interval; `rain` changes only weather. The frozen accepted IDs for the other four cases remain metadata references, not physical or legal coverage claims.
- `business_right_distance`, `signal_continuity`, and `regardless_weather` in `case-plan.json` name fixed conditions and deliberate differences. The continuous100 case is reused in all three without another planned recording.
- `signal_controller.py` requests signal state from remaining route distance. `signal_audit.py` recomputes measurements from sealed source bytes, rejects tampering or missing source, and checks fixed context in comparisons. `signal_measure.py` consumes frame-contiguous saved ego position, right-signal, actual course-change and context source fields; it hashes the exact source bytes and rejects missing context, missing frames and mismatched cases. It computes the last uninterrupted sampled signal distance before onset and does not infer the outcome from the target.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C378304__NRS-484B-413-2__motor_vehicle_driver/tests -v` passed 12 tests; see `cpu-signal-tests.log`. These are software fixture proofs only.

## Remaining CPU implementation

1. Construct a map-bound business-district right-turn route and native packet for highway, statutory frontage/building use, freight loading-zone designation and scope, and ordinary motor-vehicle driver; wire `signal_controller.py` to the CARLA signal actuator. Do not assume the catalog cell proves these facts physically.
2. Capture actual per-frame ego path and light state plus course-change onset, weather and the pinned four-camera profile. Bind the saved Native packet to `signal_measure.py` through a finalizer using the pinned write_result/converter path.
3. Author canonical stage proposals, source-hashed case diagnostics, exact constructions, risk-qualified fallback, positive and missing-source compatibility receipts, saved-only process tests, independent delivery/comparison audits and execution manifest for all five cases.
4. Review original NRS 484B.413(2) and business-district definition independently; verify the statutory 100-foot branch and weather independence against source-bound observed facts. Run exact scoped strict gate before any ready promotion.

## Proven checks and dependency boundary

`TMPDIR=$PWD/.runtime-work/c378304 MPLCONFIGDIR=$PWD/.runtime-work/c378304/mpl PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c378304 .venv-cpu/bin/python runtime.py preflight` passed (`cpu_preflight_passed: true`, Lean 4.28.0). This package has no ready proof. CARLA physical motion and camera coverage remain later GPU checks after all CPU work above. No external blocker is claimed.

Frozen witness review: one entry remains in `case-plan.json.witness_review`. The four frozen accepted metadata entries and review context were read; they report authored settings, not measured signal distance or legal coverage.

## 2026-11-23 sampled signal-distance CPU checkpoint

`signal_controller.py` now requests the right signal up to one measured 20 Hz speed step before the nominal 80/100/101-foot target. This accounts for the first retained active sample falling inside the statutory boundary when actuation begins exactly at it. The saved measurement remains authoritative; this request is not a legal cutoff or an observed fact. `prove_sampling.py` creates five diagnostic Native-shaped packets only under `.runtime-work/`, measures each with `signal_measure.py` and executes all three exact comparisons.

The diagnostic measured continuous preturn distances are short80 80.05 ft, continuous100 101.05 ft, above101 101.05 ft, interrupted 53.81 ft and rain 101.05 ft at 8 m/s and 20 Hz. The above101 target is distinct in controller policy but quantizes to the same first active sample as continuous100 at this fixture speed; actual Native source measurements must establish the contrast. Thirteen focused tests, preflight, this diagnostic proof and scoped static pass. Strict scoped gate exits 1 because status remains truthful `partial`.

Next CPU work: wire the policy with observed Native speed into a map-bound right-turn capture, retain original signal/course-change/weather/context and four-camera evidence, then implement finalization, compatibility, saved-only and independent delivery/comparison receipts.

Current log SHA-256 receipts:

- `cpu-preflight-resume.log`: `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63` (exit 0)
- `cpu-sampling-resume.log`: `cdab929d626578352906d4b815e5db058e3a6c93de55643d8d64c72bfabd8b79` (exit 0)
- `cpu-tests-resume.log`: `09f5d9061b5070cddebf8e5a3d2f1889b6c156c2f6ad500fdacb4ed5341a0fd9` (exit 0)
- `cpu-static-resume.log`: `56f7f142c56ec43f9bdb5a62d6f7f6a89966f2162c58c546ac49949dbce3d4c1` (exit 0)
- `cpu-strict-resume.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)

## 2026-11-25 source-gated Native capture and semantic draft

`native_site.py` now validates a hash-pinned original local site packet before adapter import or world mutation. It requires cited highway, district frontage/building use, loading zone, driver and route sources; checks a right-turn route with at least 140 ft of approach; and rejects diagnostic packets as original. `runner.py` preflights exact case targets, copies the reviewed source and invokes a local adapter only after validation. `native_capture.py` requests the selected signal from measured remaining route distance and speed, records actual light-state/ego-heading/weather readback for 900 continuous 20 Hz ticks, binds four original PNG camera archives by frame and hash, and removes incomplete output on failure. Fake camera tests are explicitly marked diagnostic. No CARLA site or physical turn is claimed.

`signal_measure.py` now enforces 900 original rows, 20 Hz time joins, a site hash and four camera source declarations for original packets. `signal_measure.compare` and `signal_audit.py` can verify all three source-bound numeric probes and reject equality between the measured 100 ft and 101 ft attempts. The 8 m/s diagnostic still quantizes both requests to 101.05 ft. The pairwise below/at software contrast passes, but the full numeric triple is explicitly unproved at that speed. A different local controller speed/timing may be considered only after original vehicle capability and the fixed comparison design are reviewed; the saved measured distance remains authoritative.

`build_semantics.py` generates all five canonical proposal files under `proposals/`. The stage validator progresses through case structure and presently stops at missing selected construction binding; these proposals are draft and are not reported as fully validated. Twenty focused tests pass, including missing/tampered site, wrong/right-turn route, source gate before adapter import, fake four-camera capture/cleanup and measured numeric-triple rejection. Current runtime verify, preflight, diagnostic sampling and scoped complete pass. Exact scoped strict rejects the truthful partial status. Latest logs and SHA-256 receipts are in `result.json`.

Next CPU work: implement a concrete local adapter contract for the selected source-backed car/route/signal actuator, frozen per-case construction/configuration and selected manifest; build source-hashed fixtures, measurement contracts, positive/missing-source compatibility and saved-only proofs; independently audit four-camera delivery and all three comparisons including the measured numeric triple. Original site/driver/vehicle/district evidence and physical CARLA results remain separate review inputs.

## 2026-11-25 exact construction and compatibility checkpoint

The earlier next-step paragraph above is superseded by this checkpoint. `build_constructions.py` materialized five inline exact-case primary constructions and five `fallback1` constructions. Every bundle passed `runtime.py offline` and `runtime.py compatibility` against the current runtime and Lean adapterCheck. Their selected manifest entries in `execution-manifest.json` bind exact construction hashes, offline logs, positive compatibility receipts and missing-`original-turn-signal.json` negative logs. `execution_manifest.validate` and `semantic_delivery.validate` pass. These fixtures exercise Native shape, Core conversion, full video decode and finalization; they do not establish original CARLA performance. `saved_export.py` now locates encoding scratch beneath `.runtime-work` after bundle materialization.

`prove_physical.py` ran three synthetic outcomes per exact case: measured right turn with destination road readback, incomplete turn, and missing motion evidence. `prove_lifecycle.py` exercised capture sealing, restoration, Native exit, owner release and saved-processing ordering. Five source-hashed physical preparation receipts are bound to the selected manifest. The 4 m/s 20 Hz diagnostic in `prove_sampling.py` resolves measured 100/101-foot requests, whereas its 8 m/s diagnostic aliases them; neither is an original vehicle speed or legal tolerance.

Twenty-eight focused tests pass when `TMPDIR` and `SCENARIO_PIPELINE_OUTPUT_ROOT` point under `.runtime-work/c378304`. Scoped `worker_check.py --complete` passes. Strict ready remains partial. The next gate is `delivery_handoff.validate_case`: add independent exact-case `delivery_audit.py` positive/rejected-source CPU receipts, `post_capture` saved-only proofs, and source-bound comparison audit receipts for `business_right_distance`, `signal_continuity`, and `regardless_weather`. Original site documents and CARLA motion remain local acquisition prerequisites; no original physical or legal acceptance is claimed.
