# LVMC-11-52-180-C at C375341

Actor: `motor_vehicle_driver`. Frozen cell: `alley` / `park` / `alley_entrance`.

Exact statutory source: LVMC 11.52.180(C). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: alley parking duration.

Controlled planning variable: `parked_minutes_in_rolling_hour`. Proposed requests: otherwise lawful alley parking for 25 minutes in one hour; otherwise lawful alley parking for 35 minutes in same hour. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: rolling one-hour period; otherwise lawful prerequisite.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Current CPU gap: Native runner and original one-hour ledger acquisition, current-runtime exact offline/compatibility/process-saved proofs, fallbacks, and independent audits remain unfinished. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 source-shaped construction and rolling-hour checkpoint

`.venv-cpu/bin/python runtime.py preflight` passed (`cpu_preflight_passed: true`, no simulation). The exact law measures more than thirty minutes of parking within any one-hour period, conditioned on otherwise lawful alley parking. A 30-second capture cannot alone establish that history. The two existing probes remain `planned_only`; 25 and 35 minutes are requests, not observations or verdicts.

`measure_alley_parking.py` SHA-256 `cb66e1feeef70ce9688e14b3206bce58b26d96b2b2f0b6167641fab156594fcb` joins 600 original-source-shaped Native frames to four cameras and a separately hashed parking ledger covering at least one hour. It integrates nonoverlapping parking intervals over every source-covered rolling hour, including split stays; moving within the alley does not reset prior parked time. It requires source hashes for map, alley boundary, vehicle identity, parking ledger, civil-time join, and independent otherwise-lawful review. `alley-measurement-contract.json` SHA-256 `5fdf536d69893b83dbd135231e39dac55bbddafb8bbbf85b1ad890f40ad8bd24` maps all six source observation terms. The original ledger and review remain to be acquired and independently audited.

`alley_scene.py` SHA-256 `38fdcb957fd39a3b3cd44788df0b130de8be54652d087a1e7a5633ab3d2336eb` specifies a narrow OpenDRIVE alley road, parked vehicle and hold policy, wall/curb props, and four source-camera requests. Both probes use the same scene; only the requested total parked seconds in the separate hour ledger differs. It does not assert actual surveyed alley status or an hour-long recording.

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python prove_alley_parking.py` passed 25-minute, 35-minute, exact 30-minute, and split 20-plus-15-minute numeric/source-shaped positives and nine negative source, timing, identity, and capture checks. `alley-parking-proof.json` SHA-256 `ea284cd04eaafb9b38ba30296183c10827b6ac6f8eb724098ea88cae9c969f67`.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python prove_alley_scene.py` passed two authored-scene positives and five negative checks. `alley-scene-proof.json` SHA-256 `b085dd457bea7cc2c4807e1bdee9e6da15dcca0c2ed45c68e5744804debd0966`.

Next CPU work: wire an exact Native runner and source ledger with retained civil/Native time provenance, select the first case, and pass pinned-runtime offline, positive/negative compatibility, and actual process-saved. Then test fallbacks and independent audits. Keep partial until assignment-scoped strict acceptance passes.
## 2026-11-26 selected CPU delivery preparation

Three exact selected cases use the frozen C375341 alley/park/alley_entrance cell: `__probe_1` (25 minutes), `__probe_at_30` (exactly 30 minutes), and `__probe_2` (35 minutes). One controlled comparison holds the alley, vehicle, independently reviewed otherwise-lawful source, 600-frame 20 Hz capture, four cameras, and stationary controller fixed; the one-hour ledger interval alone differs. The strict greater-than-thirty boundary was independently audited at false, false, true, with a tampered-context negative rejection. All durations are separately measured from diagnostic ledger files; requested duration never substitutes for original observation.

Exact Native construction is source-gated by `SCENARIO_ALLEY_CONTEXT` and `SCENARIO_ALLEY_LEDGER`. Original alley boundary, vehicle identity, civil-time source, lawful-parking review, 600 Native frames, four videos, and a ledger covering at least one hour must be independently supplied and hash-bound. The diagnostic fixtures are explicitly synthetic and cannot satisfy original capture, physical parking completion, pixel review, or legal acceptance.

All three current-runtime offline and public positive/missing-ledger negative chains passed on their exact construction bytes. Saved-only processing passed for each and preserved the original source. Semantic boundary probes, generic physical/lifecycle preparation tests, independent delivery positive/missing-ledger negatives, and independent controlled-comparison positive/tampered-context negative passed. Direct execution-manifest, semantic, delivery-handoff, and package receipt validators passed; assignment-scoped `--complete` passed. The generic runtime physical assessor tests travel progress, so a stationary alley capture is not claimed to satisfy that motion goal. The actual one-hour operator source and independent legal/physical review remain delivery work.

Final execution-manifest SHA-256 before strict: `0b4a07c50d0c31fa294e1012e76360291c150ff063f325862477046a9916084e`. Comparison audit spec SHA-256: `fd7258bcec3944b905376b14faeaa2c0c3f4487a7fa64775465bbdd527ad733e`. Exact scoped strict gate passed exit 0 on the selected CPU package with `--complete --require-delivery-ready`. Original source capture and legal/physical acceptance remain pending delivery.
