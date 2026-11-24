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
