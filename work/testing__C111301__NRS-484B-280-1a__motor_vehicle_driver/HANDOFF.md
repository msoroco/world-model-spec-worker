# testing__C111301__NRS-484B-280-1a__motor_vehicle_driver

Status: **partial**. The exact law is NRS 484B.280(1)(a): a motor-vehicle driver must exercise due care to avoid a collision with a pedestrian. The frozen branch is a person in a manual wheelchair at the C111301 intersection/travel/pedestrian cell. No accepted recordings or judgment range entries cover this assignment; `case-plan.json` records the frozen witness and source review. No numeric legal due-care threshold is inferred. `AGENT_PROMPT.md` is absent in this checkout; `START_HERE.md` and the worker-preparation skill supplied the active procedure.

## Exact cases and construction

- `testing__C111301__NRS-484B-280-1a__motor_vehicle_driver__wheelchair_clear_path`: same ego route and person/chair setup, pedestrian remains clear of the ego corridor.
- `testing__C111301__NRS-484B-280-1a__motor_vehicle_driver__wheelchair_crossing`: person/chair path crosses the ego corridor; original gap, braking and contact observations support physical comparison. `comparison_audit.py` rejects altered fixed conditions, missing source-bound measurements, contact, absent crossing brake response and legal verdict claims.

`runner.py` checks the grounded geometry, distinct source-confirmed person/chair bodies and an engineering-only 3-second brake response. `native_capture.py` lazily imports CARLA, checks the Native map and wheelchair prop blueprint, spawns distinct vehicle/person/chair actors, writes source-hashed original encounter and context streams, synchronized frame map and four original camera videos, and seals capture only after camera closure, actor cleanup and world-setting readback. The alternate `fallback1` broadens the Native wheelchair blueprint search if the primary exact pattern finds zero assets; it preserves the same case identity and capture contract. Actual asset availability and physical motion remain unverified until a later Native run.

`analysis.py` independently validates original encounter/context/frame-map hashes and body geometry, derives all declared channels and context evidence, writes a saved result and an analysis report, and leaves legal due care unresolved. `measurement-contract.json` binds the selected witness requirement to the saved `wheelchair_due_care_measurement`; the negative fixture removes `encounter-history.jsonl`. Diagnostic fixtures are synthetic CPU software checks and claim no physical acceptance. `delivery_audit.py` checks the sealed original files, frame/time joins, acquisition identities, physical status, saved-processing receipt and decoded video. `tests/test_delivery_audit.py` and `audit_probe.py` exercise positive and altered-source rejection.

## Passing CPU checks

- `.venv-cpu/bin/python runtime.py preflight` passed with pinned Python dependencies, ffmpeg/ffprobe, Lean and Lake 4.28.0.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C111301__NRS-484B-280-1a__motor_vehicle_driver/tests` passed **9** tests (`cpu-tests.log`).
- `semantic_check.py` passed all canonical stages (`semantic-stage-check.log`); `semantic_delivery.validate` also passed against both exact cases.
- `prove_offline.py` passed both primary exact constructions. `refresh_compatibility.py` passed both primary and both fallback exact offline/positive/negative compatibility checks, including Native result validation, Lean conversion and video decode; retained `proof-*.log`, `compat-*-receipt.json`, `compat-*-analysis.log`, and `compat-*-negative.log` are bound in `execution-manifest.json`.
- `refresh_physical.py` passed complete, incomplete and missing-evidence CPU physical fixtures and lifecycle ordering for each case. `refresh_saved.py` passed saved-only processing for each case. `prove_audit.py` passed positive and tampered-source negative audit probes for each case. These are diagnostic fixtures, not CARLA acceptance.
- Direct `execution_manifest.validate`, `semantic_delivery.validate`, `package_compatibility.check_receipts`, and `delivery_handoff.validate_case` passed together. Assignment static `worker_check.py --assignment testing__C111301__NRS-484B-280-1a__motor_vehicle_driver --complete` passed.

## Remaining worker-owned CPU work and resume actions

1. Finish the due-care judgment sweep in `semantic_author.py` and `case-plan.json` with source-backed feasible encounter distances and response range; keep legal judgment unresolved and do not invent a statutory cutoff. Rerun `semantic_author.py`, `semantic_check.py`, `construction_author.py`, `fallback_author.py` and all bound proofs after any capture-contract change.
2. Review the Native construction against the original law and witness context. Test map waypoint connectivity, manual-chair asset selection/placement and pedestrian motion with fake CARLA calls where possible; correct any missing source or capture behavior. Rerun `prove_offline.py`, `refresh_physical.py`, `refresh_compatibility.py`, `refresh_saved.py`, `prove_audit.py` after construction changes.
3. Connect the independent `comparison_audit.py` to a source-bound paired-case acceptance proof and the batch-level branch/delivery integration. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111301__NRS-484B-280-1a__motor_vehicle_driver --complete --require-delivery-ready`, then `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`; repair every CPU gate before marking `ready`. Other assigned packages remain partial and must continue in batch order.

No missing package index, Python dependency, FFmpeg, Lean or Lake tool is a current blocker. The strict gate still rejects partial packages. The independent timer publishes checkpoints; no Git command was run.
